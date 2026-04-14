from fastapi import FastAPI
from mysite.bacend import test
import  uvicorn

app = FastAPI()
app.include_router(test.collector_router)


if __name__ == '__main__':
    uvicorn.run(app , host='127.0.0.1', port=8002)
