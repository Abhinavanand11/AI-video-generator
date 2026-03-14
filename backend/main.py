from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import time
import uuid
from openai import OpenAI
from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv()

app = FastAPI(title="Sora AI Video Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
os.makedirs("backend/videos", exist_ok=True)

# In-memory job store
# Structure: { job_id: { status, progress, script, filename, error } }
jobs: dict = {}


class VideoRequest(BaseModel):
    topic: str


def run_generation(job_id: str, topic: str):
    """Background task that generates script then video."""
    try:
        # --- Stage 1: Generate Script ---
        jobs[job_id]["status"] = "generating_script"
        jobs[job_id]["progress"] = 5

        script = generate_script(topic)
        jobs[job_id]["script"] = script
        jobs[job_id]["progress"] = 20

        # --- Stage 2: Render Video ---
        jobs[job_id]["status"] = "rendering_video"
        filename = f"video_{job_id}.mp4"
        generate_video(job_id, script, filename)

        # --- Done ---
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["filename"] = filename

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)


def generate_script(topic: str) -> str:
    prompt = f"""
Write a narration script for a 10-second YouTube video about {topic}.
Requirements:
- Maximum 25 words (fit 10 seconds of narration)
- Friendly and engaging tone
- Educational
- Include simple visual cues suitable for a cartoon-style cinematic video
Style of visuals:
- colorful cartoon animation
- cinematic camera movement
- playful and engaging
Output only the narration text.
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def generate_video(job_id: str, script: str, filename: str):
    prompt = f"""
Create a cinematic educational YouTube video with narration.
Narration script: {script}
Style: cinematic, documentary, realistic visuals.
"""
    video = client.videos.create(
        model="sora-2",
        prompt=prompt,
        size="1280x720",
        seconds="12",
    )

    # Poll Sora until done
    while video.status in ("in_progress", "queued"):
        video = client.videos.retrieve(video.id)
        raw_progress = getattr(video, "progress", 0) or 0
        # Map Sora's 0-100 into our 20-99 range (script already used 0-20)
        mapped = 20 + int(raw_progress * 0.79)
        jobs[job_id]["progress"] = min(mapped, 99)
        time.sleep(2)

    if video.status == "failed":
        raise Exception("Sora video generation failed")

    content = client.videos.download_content(video.id, variant="video")
    video_path = f"videos/{filename}"
    content.write_to_file(video_path)


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "Sora AI Video Generator API is running"}


@app.post("/generate")
async def start_generation(request: VideoRequest, background_tasks: BackgroundTasks):
    """Start a video generation job. Returns job_id immediately."""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "script": None,
        "filename": None,
        "error": None,
    }
    background_tasks.add_task(run_generation, job_id, request.topic)
    return {"job_id": job_id}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Poll job status. Frontend calls this every 2 seconds."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    return {
        "status": job["status"],
        "progress": job["progress"],
        "script": job["script"],
        "error": job["error"],
    }


@app.get("/video/{job_id}")
async def get_video(job_id: str):
    """Stream the completed video file."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video not ready yet")
    video_path = f"videos/{job['filename']}"
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file missing")
    return FileResponse(video_path, media_type="video/mp4", filename=job["filename"])


# Legacy endpoints kept for compatibility
@app.post("/generate-script")
async def legacy_generate_script(request: VideoRequest):
    try:
        script = generate_script(request.topic)
        return {"script": script}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)