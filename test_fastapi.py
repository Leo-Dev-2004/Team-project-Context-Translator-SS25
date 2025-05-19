from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
import uvicorn
from pathlib import Path

app = FastAPI()

# Serve a blank favicon to prevent 404 errors
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/")
def read_root():
    return {"Hello": "World"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
