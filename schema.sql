CREATE DATABASE IF NOT EXISTS corporate_training;
USE corporate_training;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    password VARCHAR(255),
    role ENUM('user', 'admin') DEFAULT 'user'
);

CREATE TABLE topics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255)
);

CREATE TABLE materials (
    id INT AUTO_INCREMENT PRIMARY KEY,
    topic_id INT,
    content TEXT,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    topic_id INT,
    question TEXT,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE answers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question_id INT,
    answer TEXT,
    is_correct BOOLEAN,
    FOREIGN KEY (question_id) REFERENCES questions(id)
);

CREATE TABLE results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    topic_id INT,
    score INT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);
