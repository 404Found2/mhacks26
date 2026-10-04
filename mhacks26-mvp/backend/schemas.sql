PRAGMA foreign_keys = ON;

CREATE TABLE users (
    userid INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    created DATETIME DEFAULT current_timestamp
);

CREATE TABLE sessions (
    sessionid VARCHAR(36) PRIMARY KEY,
    userid INTEGER,
    FOREIGN KEY (userid) REFERENCES users(userid)
);

CREATE TABLE personas (
    sessionid VARCHAR(36),
    userid INTEGER,
    demographics VARCHAR(1000),
    habits VARCHAR(1000),
    pains VARCHAR(1000),
    created DATETIME DEFAULT current_timestamp,
    FOREIGN KEY (sessionid) REFERENCES sessions(sessionid) ON DELETE CASCADE,
    FOREIGN KEY (userid) REFERENCES users(userid),
    CONSTRAINT chk_valid CHECK ((sessionid IS NOT NULL AND userid IS NULL) OR (sessionid IS NULL AND userid IS NOT NULL))
);

CREATE TABLE messages (
    sessionid VARCHAR(36),
    userid INTEGER,
    role VARCHAR(20) NOT NULL,
    content VARCHAR(4000) NOT NULL,
    chips TEXT,
    statement VARCHAR(1000),
    kind VARCHAR(20),
    created DATETIME DEFAULT current_timestamp,
    FOREIGN KEY (sessionid) REFERENCES sessions(sessionid) ON DELETE CASCADE,
    FOREIGN KEY (userid) REFERENCES users(userid),
    CONSTRAINT chk_valid CHECK ((sessionid IS NOT NULL AND userid IS NULL) OR (sessionid IS NULL AND userid IS NOT NULL))
);

CREATE TABLE strategy (
    sessionid VARCHAR(36),
    userid INTEGER,
    statement VARCHAR(1000),
    steps VARCHAR(1000),
    created DATETIME DEFAULT current_timestamp,
    FOREIGN KEY (sessionid) REFERENCES sessions(sessionid) ON DELETE CASCADE,
    FOREIGN KEY (userid) REFERENCES users(userid),
    CONSTRAINT chk_valid CHECK ((sessionid IS NOT NULL AND userid IS NULL) OR (sessionid IS NULL AND userid IS NOT NULL))
);

CREATE TABLE products (
    sessionid VARCHAR(36),
    userid INTEGER,
    name VARCHAR(255),
    des VARCHAR(1000),
    price DECIMAL(10, 2),
    margin DECIMAL(3, 2),
    created DATETIME DEFAULT current_timestamp,
    FOREIGN KEY (sessionid) REFERENCES sessions(sessionid) ON DELETE CASCADE,
    FOREIGN KEY (userid) REFERENCES users(userid),
    CONSTRAINT chk_valid CHECK ((sessionid IS NOT NULL AND userid IS NULL) OR (sessionid IS NULL AND userid IS NOT NULL))
);

CREATE TABLE settings (
    sessionid VARCHAR(36),
    userid INTEGER,
    todos_initialized INTEGER NOT NULL DEFAULT 0,
    created DATETIME DEFAULT current_timestamp,
    FOREIGN KEY (sessionid) REFERENCES sessions(sessionid) ON DELETE CASCADE,
    FOREIGN KEY (userid) REFERENCES users(userid),
    CONSTRAINT chk_valid CHECK ((sessionid IS NOT NULL AND userid IS NULL) OR (sessionid IS NULL AND userid IS NOT NULL))
);

CREATE TABLE todos (
    sessionid VARCHAR(36),
    userid INTEGER,
    name VARCHAR(255),
    des VARCHAR(1000),
    status VARCHAR(225),
    created DATETIME DEFAULT current_timestamp,
    FOREIGN KEY (sessionid) REFERENCES sessions(sessionid) ON DELETE CASCADE,
    FOREIGN KEY (userid) REFERENCES users(userid),
    CONSTRAINT chk_valid CHECK ((sessionid IS NOT NULL AND userid IS NULL) OR (sessionid IS NULL AND userid IS NOT NULL))
);
