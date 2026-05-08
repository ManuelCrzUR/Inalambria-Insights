# 🔐 Autenticación con Google Drive

Para descargar parquets de Google Drive, necesitas crear credenciales OAuth 2.0.

## 📝 Paso 1: Crear Proyecto en Google Cloud Console

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. **Crea un nuevo proyecto:**
   - Click en selector de proyecto (arriba a la izquierda)
   - Click en "NEW PROJECT"
   - Nombre: `Twnel Pipeline`
   - Click "CREATE"
   - Espera a que se cree (1-2 min)

## 🔑 Paso 2: Habilitar Google Drive API

1. En el menú, busca **"APIs & Services"** → **"Enabled APIs & services"**
2. Click en **"+ ENABLE APIS AND SERVICES"** (botón azul arriba)
3. Busca **"Google Drive API"**
4. Click en ella y luego **"ENABLE"**

## 🎫 Paso 3: Crear credenciales OAuth 2.0

1. Ve a **"Credentials"** (en el menú izquierdo)
2. Click en **"+ CREATE CREDENTIALS"**
3. Selecciona **"OAuth client ID"**
4. Si te pide "Configure OAuth consent screen", clickea ese botón:
   - Escoge **"External"**
   - Click "CREATE"
   - **Rellena:**
     - App name: `Twnel Pipeline`
     - User support email: Tu email
     - Developer contact: Tu email
   - Click "SAVE AND CONTINUE" (sin agregar scopes)
   - Click "SAVE AND CONTINUE" (test users)
   - Click "BACK TO DASHBOARD"

5. De vuelta en Credentials, click **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
6. **Aplicación type:** Selecciona **"Desktop application"**
7. **Nombre:** `Twnel Local`
8. Click **"CREATE"**

## 💾 Paso 4: Descargar archivo JSON

1. Aparecerá una ventana con **"Download"** (botón derecho con nube)
2. Click en ese botón - descarga un JSON
3. **Renombra el archivo a:** `client_secret_drive.json`
4. **Muévelo a tu carpeta del pipeline:**
   ```
   C:\Users\manue\Desktop\Twnel\pipeline\client_secret_drive.json
   ```

## ✅ Paso 5: Verificar

Verifica que el archivo existe:
```bash
ls -la client_secret_drive.json
# client_secret_drive.json  (debe mostrar el archivo)
```

El contenido debe verse así:
```json
{
  "type": "service_account",
  "project_id": "twnel-pipeline-...",
  "private_key_id": "...",
  "client_id": "...",
  "client_secret": "...",
  ...
}
```

## 🚀 Listo!

Ahora ejecuta:
```bash
python run_pipeline_locally.py --folder-id "TU_FOLDER_ID"
```

**Primera ejecución:** Abrirá tu navegador para autorizar. Aprueba y listo.

El token se guarda en `~\.cache\twnel_drive_token.json` - futuras ejecuciones no piden autorización.

---

## 🆘 Troubleshooting

### Error: "No such file or directory: 'client_secret_drive.json'"

Verifica que:
1. El archivo existe en `C:\Users\manue\Desktop\Twnel\pipeline\`
2. El nombre es exactamente `client_secret_drive.json` (sin comillas)

### Error: "The user has not granted the application access to the Drive API"

La autenticación en el navegador falló. Reintenta:
```bash
rm ~\.cache\twnel_drive_token.json
python run_pipeline_locally.py --folder-id "TU_FOLDER_ID"
```

### Error: "Invalid folder ID"

El folder no existe o no es accesible. Verifica:
- La ID es correcta (cópiala de la URL del folder en Drive)
- El folder está en tu Drive personal (no compartido)

---

**Listo! Ya puedes descargar parquets. 🎉**
