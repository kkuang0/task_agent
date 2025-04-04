import re
from datetime import datetime, timedelta
import dateparser
from typing import Dict, List, Optional, Tuple, Any

class TimeConstraintParser:
    """Parser for extracting time constraints from natural language text."""
    
    def __init__(self):
        # Define regex patterns for different time periods
        self.patterns = {
            'end_of_year': r'(?:by|before|until|prior to|no later than)?\s*(?:the)?\s*end\s*(?:of)?\s*(?:the)?\s*year',
            'end_of_month': r'(?:by|before|until|prior to|no later than)?\s*(?:the)?\s*end\s*(?:of)?\s*(?:the)?\s*month',
            'end_of_week': r'(?:by|before|until|prior to|no later than)?\s*(?:the)?\s*end\s*(?:of)?\s*(?:the)?\s*week',
            'end_of_day': r'(?:by|before|until|prior to|no later than)?\s*(?:the)?\s*end\s*(?:of)?\s*(?:the)?\s*day',
            'next_week': r'(?:by|before|until|prior to|no later than)?\s*(?:the)?\s*next\s*week',
            'next_month': r'(?:by|before|until|prior to|no later than)?\s*(?:the)?\s*next\s*month',
            'specific_date': r'(?:by|before|until|prior to|no later than)?\s*(?:the)?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{4})?)',
            'days_from_now': r'(?:in|within)\s*(\d+)\s*days',
            'weeks_from_now': r'(?:in|within)\s*(\d+)\s*weeks',
            'months_from_now': r'(?:in|within)\s*(\d+)\s*months'
        }
    
    def extract_deadline(self, text: str) -> Optional[datetime]:
        """
        Extract deadline from text description.
        
        Args:
            text: Text containing potential deadline information
            
        Returns:
            datetime object representing the deadline, or None if no deadline found
        """
        if not text:
            return None
            
        text = text.lower()
        
        # Try to find specific date patterns first using dateparser
        specific_date_match = re.search(self.patterns['specific_date'], text)
        if specific_date_match and specific_date_match.group(1):
            date_str = specific_date_match.group(1)
            parsed_date = dateparser.parse(date_str)
            if parsed_date:
                # Set time to end of day
                return parsed_date.replace(hour=23, minute=59, second=59)
        
        # Check for relative time patterns
        now = datetime.now()
        
        if re.search(self.patterns['end_of_year'], text):
            # End of the current year
            return datetime(now.year, 12, 31, 23, 59, 59)
        
        if re.search(self.patterns['end_of_month'], text):
            # End of the current month
            if now.month == 12:
                next_month = datetime(now.year + 1, 1, 1)
            else:
                next_month = datetime(now.year, now.month + 1, 1)
            
            # Subtract one second to get the end of the current month
            return next_month - timedelta(seconds=1)
        
        if re.search(self.patterns['end_of_week'], text):
            # End of the current week (assuming week ends on Sunday)
            days_until_sunday = (6 - now.weekday()) % 7
            end_of_week = now + timedelta(days=days_until_sunday)
            return end_of_week.replace(hour=23, minute=59, second=59)
        
        if re.search(self.patterns['end_of_day'], text):
            # End of the current day
            return now.replace(hour=23, minute=59, second=59)
        
        if re.search(self.patterns['next_week'], text):
            # End of next week
            days_until_sunday = (6 - now.weekday()) % 7
            end_of_next_week = now + timedelta(days=days_until_sunday + 7)
            return end_of_next_week.replace(hour=23, minute=59, second=59)
        
        if re.search(self.patterns['next_month'], text):
            # End of next month
            if now.month < 11:
                next_next_month = datetime(now.year, now.month + 2, 1)
            elif now.month == 11:
                next_next_month = datetime(now.year + 1, 1, 1)
            else:  # month == 12
                next_next_month = datetime(now.year + 1, 2, 1)
            
            # Subtract one second to get the end of next month
            return next_next_month - timedelta(seconds=1)
        
        # Check for "X days/weeks/months from now" patterns
        days_match = re.search(self.patterns['days_from_now'], text)
        if days_match and days_match.group(1):
            num_days = int(days_match.group(1))
            return (now + timedelta(days=num_days)).replace(hour=23, minute=59, second=59)
        
        weeks_match = re.search(self.patterns['weeks_from_now'], text)
        if weeks_match and weeks_match.group(1):
            num_weeks = int(weeks_match.group(1))
            return (now + timedelta(days=num_weeks * 7)).replace(hour=23, minute=59, second=59)
        
        months_match = re.search(self.patterns['months_from_now'], text)
        if months_match and months_match.group(1):
            num_months = int(months_match.group(1))
            new_month = now.month + num_months
            new_year = now.year
            while new_month > 12:
                new_month -= 12
                new_year += 1
            
            # Handle month rollover
            try:
                result_date = now.replace(year=new_year, month=new_month)
            except ValueError:
                # Handle case where the day doesn't exist in target month
                # (e.g., February 30th)
                if new_month == 2:
                    last_day = 29 if (new_year % 4 == 0 and new_year % 100 != 0) or (new_year % 400 == 0) else 28
                elif new_month in [4, 6, 9, 11]:
                    last_day = 30
                else:
                    last_day = 31
                
                result_date = datetime(new_year, new_month, last_day)
            
            return result_date.replace(hour=23, minute=59, second=59)
        
        # Use dateparser as a last resort for any other date formats
        try:
            parsed = dateparser.parse(text, settings={'PREFER_DATES_FROM': 'future'})
            if parsed:
                return parsed
        except:
            # If dateparser fails, just return None
            pass
            
        return None
    
    def extract_task_constraints(self, tasks: List[Dict[str, Any]]) -> Dict[str, datetime]:
        """
        Extract deadline constraints from a list of tasks.
        
        Args:
            tasks: List of task dictionaries
            
        Returns:
            Dictionary mapping task IDs to deadline datetimes
        """
        task_deadlines = {}
        
        for task in tasks:
            task_id = str(task.get('id', task.get('ID', '')))
            description = task.get('description', task.get('Description', ''))
            title = task.get('title', task.get('Title', ''))
            
            # Check both title and description for deadlines
            deadline = None
            if description:
                deadline = self.extract_deadline(description)
            if not deadline and title:
                deadline = self.extract_deadline(title)
                
            if deadline:
                task_deadlines[task_id] = deadline
                
        return task_deadlines
                
    def extract_global_constraints(self, constraints: List[str]) -> Dict[str, Any]:
        """
        Extract global time constraints from constraint strings.
        
        Args:
            constraints: List of constraint strings
            
        Returns:
            Dictionary of constraint types and their values
        """
        global_constraints = {
            'project_deadline': None,
            'work_hours': {'start': 9, 'end': 17},  # Default 9-5 workday
            'weekends_off': True
        }
        
        for constraint in constraints:
            if not constraint:
                continue
                
            # Check for project deadline
            deadline = self.extract_deadline(constraint)
            if deadline:
                global_constraints['project_deadline'] = deadline
                
            # Check for work hours constraints
            work_hours_match = re.search(r'work\s+hours?(?:\s+are|\s+is)?(?:\s+from)?\s+(\d{1,2})(?::\d{2})?\s*(?:am|pm)?\s*(?:to|-)\s*(\d{1,2})(?::\d{2})?\s*(?:am|pm)?', constraint.lower())
            if work_hours_match:
                start_hour = int(work_hours_match.group(1))
                end_hour = int(work_hours_match.group(2))
                
                # Adjust for AM/PM if specified
                if 'pm' in constraint.lower() and start_hour < 12:
                    start_hour += 12
                if 'pm' in constraint.lower() and end_hour < 12:
                    end_hour += 12
                
                global_constraints['work_hours'] = {'start': start_hour, 'end': end_hour}
                
            # Check for weekend work constraints
            if re.search(r'(?:include|work\s+on)\s+weekends', constraint.lower()):
                global_constraints['weekends_off'] = False
                
            if re.search(r'(?:exclude|no\s+work\s+on)\s+weekends', constraint.lower()):
                global_constraints['weekends_off'] = True
                
        return global_constraints