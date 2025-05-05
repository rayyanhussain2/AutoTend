
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.http import HttpResponse
import sqlite3
import cv2
import numpy as np
import random
import zipfile
import os
import tempfile
import shutil
import threading
from insightface.app import FaceAnalysis
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import csv

def default(request):
    if request.method == 'GET':
        id = request.session.get('id', None)
        if (id == None):
            return HttpResponseRedirect('/login')
        return HttpResponseRedirect("/home")

def login(request):
    conn = sqlite3.connect("db.sqlite3")  # Replace with your actual database path
    if request.method == "GET":
        id = request.session.get('id', None)
        if(id == None):
            return render(request, 'login.html')
        return HttpResponseRedirect('/home')
    
    if request.method == "POST":
        usrData = request.POST.dict()
        usrID = usrData['id']
        usrPswd = usrData['password']

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM TA WHERE id = ? AND password = ?", [usrID, usrPswd])
        result = cursor.fetchone()
        cursor.close()
        print(result)
        if(result[0] == 1):
            request.session['id'] = usrID
            return HttpResponseRedirect('/home')
        else:
            return render(request, "login.html") 
            
def home(request):
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()
    id = request.session.get('id', None)
    if (id == None):
        return HttpResponseRedirect('/login') #i cant send unless the cookie is in place
    
    if request.method == 'GET':
        usrData = request.GET.dict()
        try:
            errorMsg = usrData['errorMsg']
            if errorMsg == "1":
                errorMsg = "Error: Student Not Found"
            
            elif errorMsg == "2":
                errorMsg = "Error: Student Attendance Already Marked!"

            elif errorMsg == "3":
                errorMsg = "Error Parsing Zip File!"

        except:
            errorMsg = ""

        #-------------------------------------------------GET Methods------------------------------------------------
        if 'getCSV' in usrData:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="all-data.csv"'

            writer = csv.writer(response)

            cursor.execute("SELECT id FROM Students")
            students = cursor.fetchall()
            cursor.execute("SELECT id, classTime FROM Classes Where id!=?", [-1])
            classes = cursor.fetchall()

            headRow = ["Roll No."]
            headerParse = False
            for student in students:
                writeData = [student[0]]
                for classID in classes:
                    cursor.execute("SELECT * FROM Embeddings WHERE classID=? AND studentID=?", [classID[0], student[0]])
                    if (cursor.fetchone() == None):
                        writeData.append("A")
                    else:
                        writeData.append("P")
                    
                    if not headerParse:
                        headRow.append(classID[1])
                
                if not headerParse:
                    writer.writerow(headRow)
                    headerParse = True
                
                writer.writerow(writeData)

            return response


        analytics = {}
        isAnalytics = 0
        if 'from' in usrData and 'to' in usrData:
            #classIDs
            cursor.execute("SELECT Count(id) FROM Classes WHERE classTime >= ? AND classTime <= ?", [usrData['from'], usrData['to']])
            classCount = cursor.fetchone()[0]

            #student IDs
            cursor.execute("SELECT Count(*) FROM Students")
            studentCount = cursor.fetchone()[0]

            #analytics data
            cursor.execute("""
                SELECT studentID, count(*) FROM Embeddings
                WHERE classID IN (
                    SELECT id FROM Classes
                    WHERE classTime >= ? AND classTime <= ?
                )
                GROUP BY studentID
            """, [usrData['from'], usrData['to']])

            temp = cursor.fetchall()
            studentAttendance = []
            for i in range(len(temp)):
                studentAttendance.append([temp[i][0], temp[i][1], temp[i][1] / classCount])
            
            print(studentAttendance)

            #average
            cursor.execute("""
                SELECT count(*) FROM Embeddings
                WHERE classID IN (
                    SELECT id FROM Classes
                    WHERE classTime >= ? AND classTime <= ?
                )
            """, [usrData['from'], usrData['to']]) 

            totalAttendance = cursor.fetchone()[0]

            analytics['classCount'] = classCount
            analytics['studentCount'] = studentCount
            analytics['studentAttendance'] = studentAttendance

            if classCount > 0:
                analytics['avgAttendance'] = totalAttendance/classCount 
            else:
                analytics['avgAttendance'] = 0

            isAnalytics = 1
            print(analytics)

        cursor.execute("SELECT * FROM Classes;")
        classes = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM Embeddings WHERE classID = -1")
        totalStudentCount = cursor.fetchall()[0][0]
        
        classesModified = []
        for classData in classes:
            classesModified.append([classData[0], classData[1].split(' ')]) 
            cursor.execute("SELECT COUNT(*) FROM Embeddings WHERE classID = ?", [classData[0]])
            classesModified[len(classesModified) - 1].append(cursor.fetchone()[0])
        classesModified.reverse()

        #send lock data as well - if its lockede and nothing been added yet, unlock that
        cursor.execute("SELECT write FROM Lock WHERE id = 1")
        lock = cursor.fetchall()[0][0]

        #classCount
        cursor.execute("SELECT COUNT(*) FROM Classes;")
        totalClassCount = cursor.fetchone()[0]
    
        ##Student Attendance
        studentData = []
        cursor.execute("SELECT id FROM Students;")
        students = cursor.fetchall()
        for student in students:
            studentData.append([student[0]])#rollno
            cursor.execute("SELECT COUNT(id) FROM Embeddings WHERE classID != ? AND studentID = ?;", [-1, student[0]])
            studentAttendance = cursor.fetchone()[0]
            studentData[len(studentData) - 1].append(studentAttendance)
            if totalClassCount > 0:
                studentData[len(studentData) - 1].append((studentAttendance/totalClassCount)*100)
            else:
                studentData[len(studentData) - 1].append(0)

   

        return render(request, "home.html", {'classes': classesModified, 'lock': lock, 'totalStudents': totalStudentCount, 
                                            'students': studentData, 'totalClasses': totalClassCount, 'analytics': analytics, 'studentCount': len(students), 
                                            'isAnalytics': isAnalytics, 'errorMsg': errorMsg})

    if request.method == "POST":
         #Check1 
        cursor = conn.cursor()
        cursor.execute("SELECT write FROM Lock WHERE id = 1") #even if the html is bypassed, not processing it
        result = cursor.fetchall()[0][0]
        if result:
            return HttpResponseRedirect('/')

        usrData = request.POST.dict()
        if 'gTruth' in usrData:
            #Check2
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Students;")
            if len(cursor.fetchall()) > 0:
                return HttpResponseRedirect('/')
            
            #Parsing ZipFile
            zipFile = request.FILES.get("gTruth")

            tempDir = tempfile.mkdtemp()
            tempZip = os.path.join(tempDir, 'gTruth.zip')
            try:
                with open(tempZip, 'wb') as f:
                    for chunk in zipFile.chunks():
                        f.write(chunk)

                with zipfile.ZipFile(tempZip, 'r') as f:
                    f.extractall(tempDir) 

            except:
                return HttpResponseRedirect('/home/?errorMsg=3')
            
            cursor.execute("UPDATE Lock SET write = True WHERE id = 1")
            conn.commit()
            t1 = threading.Thread(target=gTruth, args=[tempDir])
            t1.start()

            return HttpResponseRedirect('/')
        
        elif 'reset' in usrData:          
            cursor.execute("DELETE FROM Classes;")
            cursor.execute("DELETE FROM Students;")
            cursor.execute("DELETE FROM Embeddings;")
            conn.commit()
            return HttpResponseRedirect('/')
        
        elif 'addManual' in usrData:        
            rollNo = usrData['rollNo']
            classID = usrData['addManual']
            cursor.execute("SELECT Max(id) FROM Embeddings")
            embedID = cursor.fetchone()[0]
            if embedID == None:
                embedID = 0
            else:
                embedID += 1

            cursor.execute("SELECT * FROM Students WHERE id=?", [rollNo])
            temp = cursor.fetchone()
            print(temp)
            if temp == None:
                return HttpResponseRedirect('/home/?errorMsg=1')
            
            cursor.execute("SELECT * FROM Embeddings WHERE classID=? AND studentID=?", [classID, rollNo])
            temp = cursor.fetchone()
            if temp != None:
                return HttpResponseRedirect('/home/?errorMsg=2')
            
            cursor.execute("INSERT INTO Embeddings (id, classID, studentID) VALUES(?, ?, ?)", [embedID, classID, rollNo])
            conn.commit()

            return HttpResponseRedirect('/')

def lecture(request):
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()

    id = request.session.get('id', None)
    if id is None:
        return HttpResponseRedirect('/login')
    
    if request.method == 'GET':
        usrData = request.GET.dict()
        errorMsg = usrData.get('errorMsg', '')
        error_map = {
            "1": "Did not find any face!",
            "2": "Low similarity score for detected faces!"
        }
        errorMsg = error_map.get(errorMsg, "")

        classID = usrData.get('classID')
        faces = []
        
        if classID is None:
            cursor.execute("SELECT MAX(id) FROM Classes")
            try:
                classID = int(cursor.fetchall()[0][0]) + 1
            except:
                classID = 0

            cursor.execute("INSERT INTO Classes (id, classTime) VALUES (?, datetime('now'))", [classID])
            conn.commit()
        else:
            cursor.execute("SELECT id, score, path, studentID FROM Embeddings WHERE classID = ?", [classID])
            faces = [[row[0], row[1], row[2], row[3]] for row in cursor.fetchall()]

        return render(request, "class.html", {
            'classID': classID,
            'faces': faces,
            'errorMsg': errorMsg
        })
    
    if request.method == "POST":
        cursor.execute("SELECT write FROM Lock WHERE id = 1")
        if cursor.fetchall()[0][0]:
            return HttpResponseRedirect('/')
        
        usrData = request.POST.dict()
        classID = usrData['classID']
        photos = request.FILES.getlist("photos")

        # Get next embed ID
        cursor.execute("SELECT MAX(id) FROM Embeddings")
        embedID = cursor.fetchone()[0] or 0

        # Process uploaded photos
        allFaces = []
        for photo in photos:
            img = cv2.imdecode(np.frombuffer(photo.read(), np.uint8), cv2.IMREAD_COLOR)
            allFaces.extend(__getFaces(img))

        if not allFaces:
            return HttpResponseRedirect(f'/lecture/?classID={classID}&errorMsg=1')

        # Prepare face matrix (already normalized in __getFaces)
        faceMatrix = [face[1] for face in allFaces]

        # Get normalized ground truth embeddings
        cursor.execute("SELECT studentID, embedding FROM Embeddings WHERE classID=-1")
        gTruth = []
        gTruthMatrix = []
        for student in cursor.fetchall():
            embedding = pickle.loads(student[1])  # Already normalized
            gTruth.append((student[0], embedding))
            gTruthMatrix.append(embedding)

        # Compute cosine similarities using dot product
        similarity_matrix = np.dot(np.array(faceMatrix), np.array(gTruthMatrix).T)

        # Process matches
        for i in range(similarity_matrix.shape[0]):
            best_idx = np.argmax(similarity_matrix[i])
            best_score = similarity_matrix[i][best_idx]

            if best_score >= 0.4:  # Adjusted threshold from notebook
                rollNo, _ = gTruth[best_idx]
                embed = allFaces[i][1]
                path = allFaces[i][2]

                # Update or insert record
                cursor.execute("""
                    INSERT OR REPLACE INTO Embeddings (id, path, embedding, score, classID, studentID)
                    VALUES (
                        COALESCE((SELECT id FROM Embeddings 
                                WHERE classID=? AND studentID=? LIMIT 1), ?),
                        ?, ?, ?, ?, ?
                    )
                """, [
                    classID, rollNo, embedID,
                    path, pickle.dumps(embed), best_score, classID, rollNo
                ])
                embedID += 1
                
        conn.commit()
        return HttpResponseRedirect(f'/lecture/?classID={classID}')

        
        #------------------------------------------------------------------------------------

def __getFaces(cvImgObj):
    model = FaceAnalysis(name="antelopev2")
    model.prepare(ctx_id=0, det_thresh=0.3)
    
    face_data = []
    img_rgb = cv2.cvtColor(cvImgObj, cv2.COLOR_BGR2RGB)
    faces = model.get(img_rgb)
    
    for face in faces:
        bbox = list(map(int, face.bbox))
        embedding = face.embedding / np.linalg.norm(face.embedding)
        
        randomName = f"images/{randomString()}.jpg"
        path = os.path.join(os.path.dirname(_file_), 'static', randomName)
        
        croppedImg = cvImgObj[bbox[1]:bbox[3], bbox[0]:bbox[2]]
        if croppedImg.size != 0:
            cv2.imwrite(path, croppedImg)
            face_data.append([bbox, embedding, randomName])
    
    return face_data


def gTruth(dir):
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()
    subDir = os.listdir(dir)
    emID = 0
    cursor.execute("SELECT Max(id) FROM Embeddings")
    cursorResult = cursor.fetchall()[0][0]
    if cursorResult != None:
        emID = cursorResult + 1

    for file in subDir:
        if file.split('.')[1] == 'jpg':
            img = cv2.imread(dir + '/' + file)
            faces = __getFaces(img) #[[bbox, embedding, path]]
            maxSize = 0 
            maxIndex = 0
            for i in range(len(faces)):
                currSize = (faces[i][0][2] - faces[i][0][0]) * (faces[i][0][3] - faces[i][0][1]) #you need to dump the image too 
                if currSize > maxSize:
                    maxSize = currSize
                    maxIndex = i

            studentID = file.split('.')[0]
            embedBlob = pickle.dumps(faces[maxIndex][1])
            path = faces[maxIndex][2]
            cursor.execute("INSERT INTO Students (id) Values (?)", [studentID])
            cursor.execute("INSERT INTO Embeddings (id, path, embedding, classID, studentID) Values (?, ?, ?, ?, ?)", [emID, path, embedBlob, -1, studentID])
            
            emID += 1

    cursor.execute("UPDATE Lock SET write = False WHERE id = 1")
    cursor.close()
    conn.commit()
    
    shutil.rmtree(dir)

def randomString():
    import string
    result = ""
    for i in range(11):
        result += random.choice(string.ascii_letters)
    return result