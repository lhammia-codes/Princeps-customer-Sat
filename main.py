"""Application entrypoint for the Customer Satisfaction Loan Operations API.

To run the server:
    uvicorn main:app --reload
or:
    uvicorn app.main:app --reload
"""
import uvicorn
from app.main import app

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
