# Student Showcase Platform

A full-stack platform for students to showcase their projects, built with Django and React.

## Tech Stack

- **Backend:** Django 5.2
- **Database:** PostgreSQL
- **Frontend:** React + Vite

## Project Structure
## Setup Instructions

### Prerequisites

- Python 3.11+
- PostgreSQL installed and running
- pip

### 1. Clone the repository

```bash
git clone <repo-url>
cd "Student Showcase platform"
```

### 2. Create and activate virtual environment

```bash
python -m venv myvenv
myvenv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up PostgreSQL database

Open pgAdmin 4 or psql and create the database:

```sql
CREATE DATABASE showcase_db;
```

### 5. Create `.env` file

Create a `.env` file in the project root with the following:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
DB_NAME=showcase_db
DB_USER=postgres
DB_PASSWORD=your-postgres-password
DB_HOST=localhost
DB_PORT=5432
```

### 6. Run migrations

```bash
python manage.py migrate
```

### 7. Create superuser (optional)

```bash
python manage.py createsuperuser
```

### 8. Run the development server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` in your browser.

## License

This project is for academic purposes.