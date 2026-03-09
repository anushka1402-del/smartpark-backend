@echo off
cd C:\Users\LENOVO\Downloads\smartpark_mysql_backend
call venv\Scripts\activate
cd smartpark_mysql\backend
uvicorn main:app --reload --port 8001