CREATE TABLE if not exists Students(
    id VARCHAR(10) NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE if not exists Classes(
    id INT NOT NULL,
    classTime TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE if not exists Embeddings(
    id INT NOT NULL,
    path VARCHAR(100),
    embedding BLOB,
    score FLOAT,
        
    classID INT,
    studentID VARCHAR(10) NOT NULL, 
    PRIMARY KEY (id),
    FOREIGN KEY (studentID) REFERENCES Students(id),
    FOREIGN KEY (classID) REFERENCES Classes(id)
);

CREATE TABLE if not exists TA(
    id INT NOT NULL,
    password VARCHAR(20) NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE if not exists Lock(
    id INT NOT NULL,
    write BOOLEAN,
    PRIMARY KEY(id)
);