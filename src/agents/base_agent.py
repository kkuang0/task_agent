import os
from typing import Any, Dict, Optional
from pydantic import BaseModel
from mistralai import Mistral, UserMessage
from dotenv import load_dotenv
import os
import asyncio
load_dotenv()

class AgentResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None

class BaseAgent:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
        
    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process the input data and return a response
        To be implemented by child classes
        """
        raise NotImplementedError("Child classes must implement process method")
    
    def _format_prompt(self, input_data: Dict[str, Any]) -> str:
        """
        Format the input data into a prompt for the LLM
        To be implemented by child classes
        """
        raise NotImplementedError("Child classes must implement _format_prompt method")
    
    async def _call_llm(self, prompt: str) -> str:
        """
        Call the LLM with the formatted prompt
        """
        try:
            messages = [
                {"role": "system", "content": self.description},
                {"role": "user", "content": prompt}
            ]
            
            full_response = ""
            async_response = await self.client.chat.stream_async(
                model="mistral-large-latest",
                messages=messages
            )
            async for chunk in async_response:
                delta = chunk.data.choices[0].delta
                if hasattr(delta, "content") and hasattr(chunk.data.choices[0].delta, "content"):
                    delta = chunk.data.choices[0].delta.content
                else:
                    delta = chunk.choices[0].delta.content  # fallback
                if delta:
                    full_response += delta

            return full_response

        except Exception as e:
            return str(e)
            