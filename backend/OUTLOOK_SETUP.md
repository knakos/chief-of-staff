# Outlook Integration Setup

To use Outlook email integration with Chief of Staff, you need to register the application with Microsoft Azure.

## Quick Setup

1. **Run the setup script:**
   ```bash
   cd backend
   python scripts/setup_outlook.py
   ```

2. **Follow the guided setup process** - the script will walk you through:
   - Creating an Azure app registration
   - Getting your client credentials
   - Setting up API permissions
   - Configuring environment variables

3. **Restart the backend server** after setup is complete

4. **Test the integration** by typing `/outlook status` in the app

## Manual Setup (Alternative)

If you prefer to set up manually:

### 1. Azure App Registration
1. Go to [Azure Portal App Registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
2. Click "New registration"
3. Fill out:
   - **Name:** "Chief of Staff Email Integration"
   - **Account types:** "Accounts in any organizational directory and personal Microsoft accounts"
   - **Redirect URI:** `http://localhost:8787/auth/callback`
4. Click "Register"

### 2. Get Credentials
1. Copy the **Application (client) ID**
2. Copy the **Directory (tenant) ID** 
3. Go to "Certificates & secrets" → "New client secret"
4. Copy the **secret value** immediately (you can't see it again!)

### 3. API Permissions
1. Go to "API permissions" → "Add a permission" → "Microsoft Graph"
2. Choose "Delegated permissions" and add:
   - `Mail.ReadWrite`
   - `Mail.Send` 
   - `MailboxSettings.ReadWrite`
   - `offline_access`
3. Click "Grant admin consent" (important!)

### 4. Environment Variables
Add to your `.env` file:
```bash
MICROSOFT_CLIENT_ID=your-client-id-here
MICROSOFT_CLIENT_SECRET=your-client-secret-here
MICROSOFT_TENANT_ID=common
MICROSOFT_REDIRECT_URI=http://localhost:8787/auth/callback
```

## Usage

Once configured, you can use these commands:

- `/outlook status` - Check connection status
- `/outlook setup` - Create GTD folder structure  
- `/outlook sync` - Sync emails from Outlook
- `/outlook triage` - AI-process unprocessed emails
- `/triage` - Process both local and Outlook emails

## Troubleshooting

### "unauthorized_client" Error
- Make sure you've registered the app in Azure Portal
- Verify the client ID is correct in your `.env` file
- Check that the redirect URI matches exactly

### "insufficient_privileges" Error  
- You need admin consent for the API permissions
- Ask your IT admin to grant consent, or use a personal Microsoft account

### "invalid_grant" Error
- The authorization code may have expired
- Try the authorization flow again
- Check that your system clock is accurate

### Token Refresh Issues
- The app automatically refreshes tokens
- If issues persist, try `/outlook status` to re-authenticate

## Security Notes

- Client secrets should be kept secure and not shared
- The app only requests the minimum necessary permissions
- Tokens are stored temporarily in memory (consider database storage for production)
- All communication uses HTTPS for the authorization flow

## Support

If you encounter issues:
1. Check the backend server logs for detailed error messages
2. Verify all environment variables are set correctly
3. Ensure the redirect URI in Azure matches exactly: `http://localhost:8787/auth/callback`
4. Try using a personal Microsoft account if you're having enterprise permission issues