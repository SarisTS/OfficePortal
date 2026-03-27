# 🏢 Office Portal

A web-based Office Management System built to manage employee attendance, roles, and company operations efficiently.

---

## 🚀 Features

* 👨‍💼 Employee Management
* 🕒 Attendance Tracking (Check-in / Check-out)
* 📍 Geo-fencing support
* 🔐 Role-Based Access Control
* 🏢 Multi-company support
* 📊 Admin Dashboard (Planned)

---

## 🛠️ Tech Stack

### Backend

* FastAPI
* PostgreSQL
* SQLAlchemy

### Frontend

* Laravel (Migrating to Django)

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/office-portal.git
cd office-portal
```

### 2. Setup Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### 3. Setup Database

* Create PostgreSQL database
* Update `.env` file with DB credentials

### 4. Run Server

```bash
uvicorn main:app --reload
```

---

## 📡 API Endpoints

| Method | Endpoint              | Description    |
| ------ | --------------------- | -------------- |
| POST   | /login                | User Login     |
| POST   | /attendance/check-in  | Mark Check-in  |
| POST   | /attendance/check-out | Mark Check-out |

---

## 📁 Project Structure

```
OfficePortal/
│── backend/
│   ├── app/
│   ├── models/
│   ├── routes/
│   └── main.py
│
│── frontend/
│
│── README.md
```

---

## 🔮 Future Improvements

* Shift Management System
* Reports & Analytics
* Mobile App Integration
* Notification System

---

## 👨‍💻 Author

Sarish
Software Developer

---

## 📌 Notes

This project is under active development.
