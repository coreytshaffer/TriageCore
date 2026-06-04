# Expose app safely if textual is installed

try:
    from .app import TriageDeskApp
except ImportError:
    TriageDeskApp = None
