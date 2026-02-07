# CivitAI Model Auto Uploader

[中文版本](README_zh.md)

## 📋 Project Overview

This is a Python script for automatically uploading model files to the **CivitAI** platform. It provides a complete automated upload workflow, including handshake authentication, chunked upload, concurrent processing, and database synchronization, helping users quickly upload large model files.

## ✨ Key Features

- 🔐 **Secure Authentication**: Supports Cookie token and CSRF token verification
- 📦 **Smart Chunking**: Automatically splits large files into multiple chunks
- ⚡ **Concurrent Upload**: Uses 4 threads to upload chunks concurrently, significantly improving speed
- 🔄 **Auto Retry**: Failed chunks are automatically retried (up to 5 times with exponential backoff)
- 🛣️ **Route Management**: Automatically obtains and manages the dedicated route assigned by CivitAI servers
- 📊 **Progress Monitoring**: Real-time upload progress display
- 🔗 **Database Sync**: Automatically syncs to CivitAI database after upload completion

## 🚀 Quick Start

### 1. Requirements

```bash
Python 3.7+
```

### 2. Install Dependencies

```bash
pip install requests tqdm
```

### 3. Obtain Authentication Information

You need to get the following information from the CivitAI website:

1. **CIVITAI_TOKEN**: Your CivitAI authentication token
   - Visit [civitai.com](https://civitai.com)
   - Log in to your account
   - Open browser developer tools (F12)
   - Go to `Storage` → `Cookies` → `civitai.com`
   - Find the value of `__Secure-civitai-token`

2. **CSRF_TOKEN**: Cross-Site Request Forgery protection token
   - On the same Cookies page, find the value of `__Host-next-auth.csrf-token`

3. **VERSION_ID**: Model version ID
   - Find the `modelVersionId` parameter in your model page URL, or
   - Obtain it from the model editing page

### 4. Configure the Script

Edit the `auto_put.py` file and fill in your authentication information and file path:

```python
# Configuration section
CIVITAI_TOKEN = "YOUR_CIVITAI_TOKEN_HERE"
CSRF_TOKEN = "YOUR_CSRF_TOKEN_HERE"
VERSION_ID = "YOUR_MODEL_VERSION_ID_HERE"
FILE_PATH = "YOUR_FILE_PATH"  # e.g., "D:\\models\\my_model.safetensors"
```

### 5. Run the Script

```bash
python auto_put.py
```

## 📖 How It Works

### Step 0: Handshake Preparation
- Visit the model page to obtain the dedicated route assigned by the server (civitai-route)
- This "room number" is crucial for subsequent upload operations

### Step 1: Initialize Upload
- Send file information to the CivitAI API (filename, size, type, etc.)
- Server returns upload ID, key, and list of S3 chunk upload addresses

### Step 2: Concurrent Chunked Upload
- Split the file into multiple chunks (the number of chunks is determined by the number of URLs returned by S3)
- Use 4 threads to upload chunks concurrently, with automatic retry on failure
- Collect ETag for each chunk for merge verification

### Step 3: Physical Merge
- Call the `/api/upload/complete` endpoint to merge all chunks on the server side
- Server verifies ETag integrity

### Step 4: Database Synchronization
- Call `/api/trpc/modelFile.create` to sync upload information to CivitAI database
- Model becomes viewable on the web after completion

## ⚙️ Advanced Configuration

### Hardcoded UUID (Optional)

If step B (database sync) returns a 500 or UNAUTHORIZED error, you can manually specify a UUID:

```python
HARDCODED_UUID = "f5ebae8f-xxxx-xxxx-xxxx-xxxxxxxxxxxx"  # Obtained from packet capture tools
```

When not set, the script automatically uses `uuid` or `uploadId` from the initialization response.

## 🔧 Troubleshooting

### Q: How to resolve "500 Internal Server Error"?

**A:** This is usually a routing issue. Try:
- Confirm that `civitai-route` is correctly set in Cookies
- Restart the script to re-obtain the route
- Check if Cookies have expired

### Q: What if the upload is interrupted due to network issues?

**A:** The script has an automatic retry mechanism that retries each chunk up to 5 times. If all attempts fail, please:
- Check your network connection
- Re-run the script (will start from the beginning)

### Q: How to improve upload speed?

**A:** You can modify the number of threads in the script:

```python
with ThreadPoolExecutor(max_workers=8) as executor:  # Change to 8 threads
```

However, be careful not to exceed server limits.

### Q: Are there any restrictions on uploaded file formats?

**A:** Based on the code, supported types include:
- `Model` (model files such as `.safetensors`, `.ckpt`)
- Supports metadata configuration: format, precision, size, etc.

## 🛡️ Security Notes

- 🚨 **Do not share your Token and CSRF Token**
- Keep your configuration file safe; consider excluding versions with sensitive information in `.gitignore`
- Consider using environment variables instead of hardcoding configuration

## 🐛 Debugging Tips

If you encounter issues, the script will print detailed log messages:

```
📡 Getting dedicated route from server...
✅ Handshake complete! Assigned route: xxx-xxx-xxx
🚀 Starting file upload (4 threads + auto retry)...
[progress bar display]
✅ Physical file merge successful!
...
```

These logs can help identify problems.

## 📝 License

This project is for learning and personal use only. Please read CivitAI's Terms of Service and Usage Policy before using.

## 💬 Feedback

Feel free to submit issues or suggestions!

---

*Last Updated: 2026.02.07*
