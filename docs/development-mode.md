# Development Mode - Authentication Bypass

This document explains how to use development mode to bypass authentication during local development.

---

## Overview

The platform supports a **development mode** that automatically disables authentication when the `UI_PASSWORD` environment variable is not set. This makes local development easier by removing the login requirement.

---

## How It Works

### Backend (API)

When `UI_PASSWORD` is not set in the environment:

1. **Password verification** accepts any password
   ```python
   # api/auth.py:44-46
   if not UI_PASSWORD:
       # Development mode: allow any password if UI_PASSWORD not set
       return True
   ```

2. **JWT validation** is skipped for all protected endpoints
   ```python
   # api/auth.py:107-109
   if not UI_PASSWORD:
       return {"authenticated": True, "dev_mode": True}
   ```

### Frontend (Web UI)

The frontend automatically detects development mode by:

1. Attempting to access a protected endpoint (`/api/info`) without authentication
2. If it succeeds (200 response), development mode is active
3. Sets authentication state to `true` without requiring login

```typescript
// web-ui/src/lib/auth-context.tsx:40-57
async function checkDevMode() {
  try {
    const response = await axios.get(`${API_URL}/api/info`);
    if (response.status === 200) {
      console.log('🔓 Development mode detected - authentication disabled');
      setIsAuthenticated(true);
      setToken('dev-mode');
    }
  } catch (error) {
    console.log('🔒 Production mode - authentication required');
  }
}
```

---

## Enabling Development Mode

### Option 1: No Environment Variables (Default)

Simply run the API server **without** setting `UI_PASSWORD`:

```bash
# Start API without UI_PASSWORD
python api/start_api.py

# Start Web UI
cd web-ui && npm run dev
```

**Result:** Authentication is disabled, you can access all pages directly.

### Option 2: Empty UI_PASSWORD

Set `UI_PASSWORD` to an empty string in your `.env` file:

```bash
# .env
UI_PASSWORD=
SECRET_KEY=dev-secret-key
```

**Result:** Same as Option 1 - authentication is disabled.

---

## Disabling Development Mode (Production)

To enable authentication (production mode), set a password:

```bash
# .env
UI_PASSWORD=your-secure-password-here
SECRET_KEY=your-secret-jwt-key-here
```

**Result:**
- Login page appears
- Users must enter the correct password
- JWT tokens required for all API calls

---

## Visual Indicators

### Console Messages

**Development Mode:**
```
🔓 Development mode detected - authentication disabled
```

**Production Mode:**
```
🔒 Production mode - authentication required
```

### Browser Behavior

**Development Mode:**
- No redirect to `/login`
- Direct access to all pages
- No authentication header in API calls

**Production Mode:**
- Redirects to `/login` when not authenticated
- Returns to original URL after login
- JWT token in `Authorization` header

---

## Security Notes

⚠️ **Important Security Considerations:**

1. **Never deploy with UI_PASSWORD unset**
   - Development mode should only be used locally
   - Always set UI_PASSWORD in production environments

2. **Environment variable checks**
   - The `.env` file should be in `.gitignore`
   - Use `.env.example` for documentation
   - Set production secrets via deployment platform

3. **Development mode detection**
   - Frontend auto-detects backend mode
   - No manual configuration needed
   - Works seamlessly in both modes

---

## Testing Both Modes Locally

### Test Development Mode

```bash
# 1. Remove UI_PASSWORD from .env (or leave it empty)
# .env
# UI_PASSWORD=

# 2. Restart servers
python api/start_api.py
cd web-ui && npm run dev

# 3. Visit http://localhost:3000
# Expected: Direct access to dashboard, no login required
```

### Test Production Mode

```bash
# 1. Set UI_PASSWORD in .env
# .env
UI_PASSWORD=test123
SECRET_KEY=dev-secret-key

# 2. Restart servers
python api/start_api.py
cd web-ui && npm run dev

# 3. Visit http://localhost:3000
# Expected: Redirects to /login, requires password
```

---

## Troubleshooting

### Issue: Still seeing login page in dev mode

**Check:**
1. Is `UI_PASSWORD` actually unset?
   ```bash
   # In .env file, make sure line is commented or removed:
   # UI_PASSWORD=
   ```

2. Did you restart the API server?
   ```bash
   # Stop and restart
   python api/start_api.py
   ```

3. Clear browser localStorage
   ```javascript
   // In browser console:
   localStorage.clear();
   location.reload();
   ```

### Issue: Getting 401 errors in dev mode

**Check:**
1. API server environment variables
   ```bash
   # Check if UI_PASSWORD is set
   echo $UI_PASSWORD  # Should be empty
   ```

2. API server logs
   ```bash
   # Look for development mode message
   # Should see: Development mode: authentication disabled
   ```

3. Frontend console
   ```javascript
   // Should see in console:
   // 🔓 Development mode detected - authentication disabled
   ```

---

## Code References

### Backend Files

- [api/auth.py:34-48](../api/auth.py) - `verify_password()` with dev mode check
- [api/auth.py:94-128](../api/auth.py) - `get_current_user()` with dev mode bypass

### Frontend Files

- [web-ui/src/lib/auth-context.tsx:23-57](../web-ui/src/lib/auth-context.tsx) - Dev mode detection
- [web-ui/src/lib/api.ts:55-76](../web-ui/src/lib/api.ts) - Dev mode token handling

---

## Environment Variables

| Variable | Development | Production | Description |
|----------|------------|------------|-------------|
| `UI_PASSWORD` | (unset or empty) | `secure-password` | Enables/disables authentication |
| `SECRET_KEY` | `dev-secret-key` | `random-secret-key` | JWT signing key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24h) | `1440` (24h) | Token expiration |

---

## Best Practices

### Development
✅ Don't set `UI_PASSWORD` for local development
✅ Use `.env.example` to document required variables
✅ Add `.env` to `.gitignore`
✅ Test both modes before deploying

### Production
✅ Always set strong `UI_PASSWORD`
✅ Use environment-specific secrets
✅ Never commit passwords to git
✅ Use deployment platform's secret management

---

## Related Documentation

- [docs/deployment-guide.md](deployment-guide.md) - Production deployment
- [api/README.md](../api/README.md) - API documentation
- [CLAUDE.md](../CLAUDE.md) - Platform overview
