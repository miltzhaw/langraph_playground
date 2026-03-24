// Create database and user for Flowcept 

db = db.getSiblingDB('flowcept_db'); 

db.createCollection('tasks'); 

db.createCollection('activities'); 

db.createCollection('entities'); 

db.createCollection('relations'); 

db.createCollection('agents'); 

  

// Create indexes for performance 

db.tasks.createIndex({ "activity_id": 1 }); 

db.tasks.createIndex({ "workflow_id": 1 }); 

db.tasks.createIndex({ "agent_id": 1 }); 

db.activities.createIndex({ "timestamp": 1 }); 

print("MongoDB initialized for Flowcept"); 


