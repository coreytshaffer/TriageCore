import tempfile
import py_compile
import os
import re

class PythonSyntaxValidator:
    """
    Quality gate that verifies the syntax of generated Python code
    before allowing it to be returned as a success.
    """
    
    @staticmethod
    def validate(code_output: str) -> bool:
        """
        Takes raw Python code, writes it to a secure temporary file,
        and uses native py_compile to check for syntax errors without executing it.
        Returns True if syntax is valid, False otherwise.
        """
        # Clean up markdown code blocks
        code_output = re.sub(r'^```[a-zA-Z]*\s*', '', code_output)
        code_output = re.sub(r'\s*```$', '', code_output)
        code_output = code_output.strip()
        
        # Write to a secure temp file
        fd, path = tempfile.mkstemp(suffix=".py")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(code_output)
            # The file is closed automatically by the 'with' block context manager, 
            # which closes the underlying file descriptor.
            
            # Attempt to compile safely without open handles
            py_compile.compile(path, doraise=True)
            return True
            
        except py_compile.PyCompileError as e:
            print(f"[Validator] Syntax error detected: {e}")
            return False
        finally:
            os.remove(path)
