from typing import Any, Dict, List
from .base_agent import BaseAgent, AgentResponse
from pydantic import BaseModel
import chromadb
from chromadb.config import Settings
import json
from datetime import datetime
from src.utils.json_helpers import extract_json_block
from src.utils.database import add_note, update_note, get_note, get_task_notes, delete_note
from sqlalchemy.orm import Session

class NoteInput(BaseModel):
    task_id: str
    title: str
    content: str
    tags: List[str] = []

class NoteUpdateInput(BaseModel):
    note_id: int
    title: str = None
    content: str = None
    tags: List[str] = None

class NoteQueryInput(BaseModel):
    task_id: str = None
    query: str = None
    tags: List[str] = []
    limit: int = 5

class NoteManager(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Note Manager",
            description="You are a note manager that helps organize and retrieve notes related to tasks and projects."
        )
        self.client = chromadb.EphemeralClient()
        self.collection = self.client.get_or_create_collection("task_notes")
    
    def _format_create_prompt(self, input_data: Dict[str, Any]) -> str:
        note = input_data.get("note", {})
        
        prompt = f"""
        Task ID: {note.get('task_id', '')}
        Note Title: {note.get('title', '')}
        Note Content: {note.get('content', '')}
        Tags: {', '.join(note.get('tags', []))}
        
        Please analyze this note content and provide a JSON response with the following structure:
        {{
            "summary": "<short summary of the note>",
            "key_points": ["<key point 1>", "<key point 2>", ...],
            "suggested_tags": ["<tag 1>", "<tag 2>", ...],
            "related_tasks": ["<potential related task description 1>", "<potential related task description 2>", ...]
        }}
        
        Provide concise, actionable insights in each section.
        """
        return prompt
    
    def _format_search_prompt(self, input_data: Dict[str, Any]) -> str:
        query = input_data.get("query", {})
        notes = input_data.get("notes", [])
        
        notes_text = []
        for i, note in enumerate(notes):
            tags = note.get("tags", [])
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except:
                    tags = []
            
            notes_text.append(f"""
            Note {i+1}:
            Title: {note.get('title', '')}
            Content: {note.get('content', '')}
            Tags: {', '.join(tags) if tags else 'None'}
            Created: {note.get('created_at', '')}
            """)
        
        prompt = f"""
        Search Query: {query.get('query', '')}
        Task ID: {query.get('task_id', 'Any')}
        Tags Filter: {', '.join(query.get('tags', [])) if query.get('tags') else 'None'}
        
        Notes Found:
        {"".join(notes_text)}
        
        Please analyze these notes based on the search query and provide a JSON response with the following structure:
        {{
            "relevance_ranking": [
                {{
                    "note_index": <1-based index of note>,
                    "relevance_score": <0-1 score>,
                    "matching_factors": ["<factor 1>", "<factor 2>", ...]
                }},
                ...
            ],
            "summary": "<summary of search results>",
            "recommendations": {{
                "note_organization": ["<recommendation 1>", "<recommendation 2>", ...],
                "suggested_actions": ["<action 1>", "<action 2>", ...]
            }}
        }}
        
        Provide insightful analysis based on the search query.
        """
        return prompt
    
    def _store_note_embedding(self, note):
        # Extract data for embedding
        note_data = {
            "note_id": note.id,
            "task_id": note.task_id,
            "title": note.title,
            "content": note.content,
            "tags": note.tags,
            "created_at": note.created_at.isoformat() if hasattr(note.created_at, "isoformat") else str(note.created_at)
        }
        
        # Store in ChromaDB for vector search
        self.collection.add(
            documents=[json.dumps(note_data)],
            metadatas=[{
                "note_id": str(note.id),
                "task_id": note.task_id,
                "tags": json.dumps(note.tags) if isinstance(note.tags, list) else note.tags,
                "timestamp": note.created_at.isoformat() if hasattr(note.created_at, "isoformat") else str(note.created_at)
            }],
            ids=[f"note_{note.id}"]
        )
    
    def _search_notes(self, query: str, filters: Dict = None, limit: int = 5) -> List[Dict]:
        # Query similar notes from ChromaDB
        filter_dict = {}
        if filters:
            if filters.get("task_id"):
                filter_dict["task_id"] = filters["task_id"]
        
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where=filter_dict if filter_dict else None
        )
        
        similar_notes = []
        if results.get('documents') and len(results['documents']) > 0:
            for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
                try:
                    note_data = json.loads(doc)
                    similar_notes.append({
                        **note_data,
                        **metadata
                    })
                except json.JSONDecodeError:
                    pass
        
        return similar_notes
    
    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        try:
            action = input_data.get("action", "")
            db_session = input_data.get("db_session")
            
            if action == "create":
                # Create a new note
                note_data = input_data.get("note", {})
                if not note_data.get("task_id") or not note_data.get("title") or not note_data.get("content"):
                    return AgentResponse(success=False, error="Missing required fields for note creation")
                
                # Add note to database
                note = add_note(db_session, note_data)
                
                # Store in vector DB for searching
                self._store_note_embedding(note)
                
                # Get LLM analysis
                prompt = self._format_create_prompt({"note": note_data})
                raw_response = await self._call_llm(prompt)
                
                try:
                    analysis_json = extract_json_block(raw_response)
                    if not analysis_json:
                        analysis_json = raw_response.strip()
                    
                    analysis_data = json.loads(analysis_json)
                except Exception as e:
                    analysis_data = {"error": str(e), "raw_response": raw_response}
                
                return AgentResponse(
                    success=True,
                    data={
                        "note": {
                            "id": note.id,
                            "task_id": note.task_id,
                            "title": note.title,
                            "content": note.content,
                            "tags": note.tags,
                            "created_at": note.created_at.isoformat() if hasattr(note.created_at, "isoformat") else str(note.created_at),
                            "updated_at": note.updated_at.isoformat() if hasattr(note.updated_at, "isoformat") else str(note.updated_at)
                        },
                        "analysis": analysis_data
                    }
                )
                
            elif action == "update":
                # Update an existing note
                update_data = input_data.get("update", {})
                if not update_data.get("note_id"):
                    return AgentResponse(success=False, error="Missing note_id for update")
                
                # Update note in database
                note = update_note(db_session, update_data.get("note_id"), update_data)
                if not note:
                    return AgentResponse(success=False, error="Note not found")
                
                # Update in vector DB
                self._store_note_embedding(note)
                
                return AgentResponse(
                    success=True,
                    data={
                        "note": {
                            "id": note.id,
                            "task_id": note.task_id,
                            "title": note.title,
                            "content": note.content,
                            "tags": note.tags,
                            "created_at": note.created_at.isoformat() if hasattr(note.created_at, "isoformat") else str(note.created_at),
                            "updated_at": note.updated_at.isoformat() if hasattr(note.updated_at, "isoformat") else str(note.updated_at)
                        }
                    }
                )
                
            elif action == "get":
                # Get a specific note or notes for a task
                note_id = input_data.get("note_id")
                task_id = input_data.get("task_id")
                
                if note_id:
                    # Get a specific note
                    note = get_note(db_session, note_id)
                    if not note:
                        return AgentResponse(success=False, error="Note not found")
                    
                    return AgentResponse(
                        success=True,
                        data={
                            "note": {
                                "id": note.id,
                                "task_id": note.task_id,
                                "title": note.title,
                                "content": note.content,
                                "tags": note.tags,
                                "created_at": note.created_at.isoformat() if hasattr(note.created_at, "isoformat") else str(note.created_at),
                                "updated_at": note.updated_at.isoformat() if hasattr(note.updated_at, "isoformat") else str(note.updated_at)
                            }
                        }
                    )
                
                elif task_id:
                    # Get all notes for a task
                    notes = get_task_notes(db_session, task_id)
                    note_list = []
                    
                    for note in notes:
                        note_list.append({
                            "id": note.id,
                            "task_id": note.task_id,
                            "title": note.title,
                            "content": note.content,
                            "tags": note.tags,
                            "created_at": note.created_at.isoformat() if hasattr(note.created_at, "isoformat") else str(note.created_at),
                            "updated_at": note.updated_at.isoformat() if hasattr(note.updated_at, "isoformat") else str(note.updated_at)
                        })
                    
                    return AgentResponse(
                        success=True,
                        data={"notes": note_list}
                    )
                
                else:
                    return AgentResponse(success=False, error="Missing note_id or task_id for retrieval")
                
            elif action == "search":
                # Search for notes
                query_data = input_data.get("query", {})
                
                # Get notes from vector DB
                search_query = query_data.get("query", "")
                filters = {
                    "task_id": query_data.get("task_id")
                } if query_data.get("task_id") else None
                
                limit = query_data.get("limit", 5)
                
                similar_notes = self._search_notes(
                    query=search_query,
                    filters=filters,
                    limit=limit
                )
                
                # Get LLM analysis
                if similar_notes:
                    prompt = self._format_search_prompt({
                        "query": query_data,
                        "notes": similar_notes
                    })
                    raw_response = await self._call_llm(prompt)
                    
                    try:
                        analysis_json = extract_json_block(raw_response)
                        if not analysis_json:
                            analysis_json = raw_response.strip()
                        
                        analysis_data = json.loads(analysis_json)
                    except Exception as e:
                        analysis_data = {"error": str(e), "raw_response": raw_response}
                else:
                    analysis_data = {"message": "No notes found matching the search criteria"}
                
                return AgentResponse(
                    success=True,
                    data={
                        "notes": similar_notes,
                        "analysis": analysis_data
                    }
                )
                
            elif action == "delete":
                # Delete a note
                note_id = input_data.get("note_id")
                if not note_id:
                    return AgentResponse(success=False, error="Missing note_id for deletion")
                
                # Delete from database
                success = delete_note(db_session, note_id)
                
                # Delete from vector DB
                try:
                    self.collection.delete(ids=[f"note_{note_id}"])
                except:
                    pass
                
                return AgentResponse(
                    success=success,
                    data={"message": "Note deleted successfully"} if success else None,
                    error="Failed to delete note" if not success else None
                )
                
            else:
                return AgentResponse(success=False, error=f"Unknown action: {action}")

        except Exception as e:
            return AgentResponse(success=False, error=str(e))

    async def summarize_note(self, note_content: str) -> str:
        """Summarize the note content using an LLM API."""
        prompt = f"Summarize the following note: {note_content}"
        response = await self._call_llm(prompt)
        return response.strip() 