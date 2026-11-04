from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'db'),
    'database': os.getenv('DB_NAME', 'myappdb'),
    'user': os.getenv('DB_USER', 'dbuser'),
    'password': os.getenv('DB_PASSWORD', 'dbpassword')
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"Database connection error: {e}")
        return None

@app.route('/api')
def hello():
    return jsonify(message="👋 Hello from the Backend API!")

@app.route('/api/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    if not conn:
        return jsonify(error="Database connection failed"), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        
        for user in users:
            if user['created_at']:
                user['created_at'] = user['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(users=users, count=len(users))
    except Error as e:
        return jsonify(error=str(e)), 500

@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.get_json()
    
    if not data or not data.get('name') or not data.get('email'):
        return jsonify(error="Name and email are required"), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify(error="Database connection failed"), 500
    
    try:
        cursor = conn.cursor()
        query = "INSERT INTO users (name, email, phone, role) VALUES (%s, %s, %s, %s)"
        values = (
            data.get('name'),
            data.get('email'),
            data.get('phone', ''),
            data.get('role', 'User')
        )
        cursor.execute(query, values)
        conn.commit()
        
        new_user_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        return jsonify(
            message="User added successfully",
            user_id=new_user_id
        ), 201
    except Error as e:
        if 'Duplicate entry' in str(e):
            return jsonify(error="Email already exists"), 409
        return jsonify(error=str(e)), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_db_connection()
    if not conn:
        return jsonify(error="Database connection failed"), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify(error="User not found"), 404
        
        cursor.close()
        conn.close()
        return jsonify(message="User deleted successfully"), 200
    except Error as e:
        return jsonify(error=str(e)), 500

@app.route('/api/health')
def health():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            conn.close()
            return jsonify(status="healthy", database="connected")
        except:
            return jsonify(status="unhealthy", database="error"), 500
    return jsonify(status="unhealthy", database="disconnected"), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)