"""Start Career Test Drive:  python app.py   then open http://127.0.0.1:8000"""

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"\n  Career Test Drive is running → http://127.0.0.1:{port}\n")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, reload=False, log_level="warning")
