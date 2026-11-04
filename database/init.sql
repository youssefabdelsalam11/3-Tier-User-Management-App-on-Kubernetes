CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    role VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO users (name, email, phone, role) VALUES
    ('Alice Johnson', 'alice@example.com', '+1-555-0101', 'Developer'),
    ('Bob Smith', 'bob@example.com', '+1-555-0102', 'Designer'),
    ('Charlie Davis', 'charlie@example.com', '+1-555-0103', 'Manager');