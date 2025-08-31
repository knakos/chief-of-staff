# Windows Setup Guide for COM Outlook Integration

## Prerequisites
- Windows machine with Outlook installed and running
- `knakos@nbg.gr` account configured in Outlook
- Python 3.8+ installed
- Node.js installed
- Git installed

## Step-by-Step Setup

### 1. Clone the Repository
```cmd
# Open Command Prompt or PowerShell as Administrator
git clone https://github.com/knakos/chief-of-staff.git
cd chief-of-staff
```

### 2. Backend Setup
```cmd
# Navigate to backend
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install Windows COM support
pip install pywin32

# Copy environment file (you should have this from your working setup)
# Make sure .env contains your working MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET
copy .env.example .env
# Edit .env with your actual values
```

### 3. Frontend Setup
```cmd
# Open a new Command Prompt/PowerShell
cd chief-of-staff\electron

# Install Node.js dependencies
npm install
```

### 4. Start the Application

#### Terminal 1 - Backend:
```cmd
cd chief-of-staff\backend
.venv\Scripts\activate
python -m uvicorn app:app --host 127.0.0.1 --port 8787 --reload
```

#### Terminal 2 - Frontend:
```cmd
cd chief-of-staff\electron
npm run dev
```

### 5. Test COM Connection

1. **Make sure Outlook is running** with `knakos@nbg.gr` logged in
2. **In the Chief of Staff app, type:** `/outlook connect`
3. **Expected result:** "Connected to local Outlook application (Method: com)"

### 6. Setup GTD Folders
```
/outlook setup
```
This will create under Inbox:
- COS_Actions
- COS_Assigned  
- COS_ReadLater
- COS_Reference
- COS_Archive

Note: Projects and tasks are linked via email extended properties, not separate folders.

### 7. Sync and Process Emails
```
/outlook sync    # Download emails to database
/triage         # AI processes and organizes emails
```

## Available Commands

| Command | Description |
|---------|-------------|
| `/outlook connect` | Try COM first, fallback to Graph API |
| `/outlook info` | Show connection details |
| `/outlook status` | Check Graph API status |
| `/outlook sync` | Sync emails using active connection |
| `/outlook setup` | Create GTD folder structure |
| `/outlook triage` | Process unprocessed emails |
| `/outlook disconnect` | Clear authentication |

## Troubleshooting

### COM Connection Issues:
- **Outlook not running:** Start Outlook and make sure `knakos@nbg.gr` is logged in
- **Permission errors:** Run Command Prompt as Administrator
- **pywin32 not working:** Try `python -m pip install --upgrade pywin32`

### If COM Fails:
The system will automatically fall back to Graph API. You can still use your existing OAuth connection.

### Port Issues:
If port 8787 is in use:
```cmd
python -m uvicorn app:app --host 127.0.0.1 --port 8788 --reload
```
Then update the frontend to connect to port 8788.

## Expected Workflow

1. **Connect:** `/outlook connect` → "Connected to local Outlook application"
2. **Setup:** `/outlook setup` → Creates GTD folders in your Outlook
3. **Sync:** `/outlook sync` → Downloads emails from `knakos@nbg.gr` inbox
4. **Process:** `/triage` → AI analyzes and organizes emails into appropriate folders
5. **Verify:** Check your Outlook Inbox - emails should be moved to COS_Actions, COS_Assigned, etc.

## Benefits of COM Connection

✅ **Direct access** to `knakos@nbg.gr` without OAuth  
✅ **Real-time folder operations** - see changes in Outlook immediately  
✅ **No Azure permissions needed** - bypasses corporate restrictions  
✅ **Full account access** - works with any account logged into Outlook  
✅ **Faster operations** - no network API calls  

## Next Steps

Once COM connection is working:
1. Test email organization with `/triage`
2. Create projects and link emails to them
3. Use `/outlook triage` for ongoing email processing
4. Explore AI-powered email summaries and task extraction

The system will automatically organize your `knakos@nbg.gr` emails using AI analysis and GTD methodology!