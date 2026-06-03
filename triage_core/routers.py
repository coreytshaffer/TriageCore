class TriageRouter:
    """
    Evaluates task complexity and determines whether a task should be 
    sent to the local TriageEngine, or bypassed entirely to the cloud.
    """
    
    @staticmethod
    def should_offload(prompt: str, data: str) -> bool:
        """
        Simple heuristic router:
        - If the combined prompt and data size is extremely large, 
          it may exceed local context limits or generation capability.
        - If the prompt requests complex architecture or reasoning, 
          it should bypass.
          
        For MVP, we offload by default to allow the Engine's timeout 
        mechanism to act as the primary fallback.
        """
        # Example heuristic: if data is > 10,000 characters, it might be too large for local
        if len(data) > 10000:
            return False
            
        # Example heuristic: bypass if keywords imply architecture design
        bypass_keywords = ["architect", "system design", "from scratch", "evaluate framework"]
        prompt_lower = prompt.lower()
        if any(keyword in prompt_lower for keyword in bypass_keywords):
            return False
            
        return True
