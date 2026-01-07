
from fastapi import FastAPI
import uvicorn
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

# Load environment variables
load_dotenv()

# Configuration from environment variables
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
MAX_WORKERS = multiprocessing.cpu_count()

# Global resources
executor: ProcessPoolExecutor | None = None
manager: multiprocessing.Manager | None = None

def init_resources():
    """Initializes the global ProcessPoolExecutor and Manager safely."""
    global executor, manager, MAX_WORKERS
    
    if executor is not None and manager is not None:
        return 

    print(f"Initializing ProcessPoolExecutor with {MAX_WORKERS} workers and Manager...")
    try:
        mp_context = multiprocessing.get_context('spawn')
        # max_tasks_per_child argument was added in Python 3.11. Removing it for compatibility.
        import sys
        if sys.version_info >= (3, 11):
            executor = ProcessPoolExecutor(max_workers=MAX_WORKERS, mp_context=mp_context,max_tasks_per_child=1)
        else:
            executor = ProcessPoolExecutor(max_workers=MAX_WORKERS, mp_context=mp_context)
            
        manager = multiprocessing.Manager()
        print("Resources initialized successfully.")
    except Exception as e:
        print(f"Critical error during resource initialization: {e}")
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles initialization (startup) and cleanup (shutdown) of resources.
    """
    # STARTUP: Initialize multiprocessing resources
    init_resources()
    
    # YIELD: Application is now ready to receive traffic
    yield
    
    # SHUTDOWN: Cleanly shut down resources
    global executor, manager
    
    print("Executing application shutdown...")
    if executor:
        print("Shutting down ProcessPoolExecutor...")
        executor.shutdown(wait=True)
    if manager:
        print("Shutting down Manager...")
        manager.shutdown()

app = FastAPI(lifespan=lifespan)

# Import and include routers here later
# from app.api.v1.endpoints import crawler_controller
# app.include_router(crawler_controller.router, prefix="/api/v1")

if __name__ == "__main__":
    # No need for sys.platform.startswith('win') check here, 
    # as init_resources handles the 'spawn' context.
    try:
        multiprocessing.set_start_method('spawn', force=True) 
    except RuntimeError:
        pass
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
