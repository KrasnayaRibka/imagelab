# Uppy Companion Server

Companion сервер для Uppy, который позволяет загружать файлы из облачных хранилищ:
- Google Drive
- Google Photos
- Dropbox
- OneDrive

## Быстрый старт

### 1. Настройка переменных окружения

Добавьте следующие переменные в ваш `.env` файл:

```env
# Companion Server Configuration
COMPANION_PORT=3020
COMPANION_PROTOCOL=http
COMPANION_DOMAIN=localhost:3020
COMPANION_SECRET=your-secret-key-change-in-production
COMPANION_ALLOWED_HOSTS=http://localhost:8000,http://localhost:3020

# Google Drive & Photos (опционально)
COMPANION_GOOGLE_KEY=your-google-client-id
COMPANION_GOOGLE_SECRET=your-google-client-secret

# Dropbox (опционально)
COMPANION_DROPBOX_KEY=your-dropbox-app-key
COMPANION_DROPBOX_SECRET=your-dropbox-app-secret

# OneDrive (опционально)
COMPANION_ONEDRIVE_KEY=your-onedrive-client-id
COMPANION_ONEDRIVE_SECRET=your-onedrive-client-secret

# Дополнительные настройки
COMPANION_MAX_FILE_SIZE=100MB
COMPANION_LOG_LEVEL=info
```

### 2. Получение OAuth ключей

#### Google Drive & Photos

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите следующие API:
   - Google Drive API
   - Google Photos Library API (для Google Photos)
4. Создайте OAuth 2.0 Client ID:
   - Тип: Web application
   - Authorized JavaScript origins: `http://localhost:3020` (для разработки)
   - Authorized redirect URIs: `http://localhost:3020/drive/redirect` и `http://localhost:3020/google/redirect`
5. Скопируйте Client ID и Client Secret в `.env`

#### Dropbox

1. Перейдите в [Dropbox App Console](https://www.dropbox.com/developers/apps)
2. Создайте новое приложение:
   - Choose an API: Scoped access
   - Choose the type of access: Full Dropbox
   - Название: любое
3. В настройках приложения добавьте Redirect URI: `http://localhost:3020/dropbox/redirect`
4. Скопируйте App key и App secret в `.env`

#### OneDrive

1. Перейдите в [Azure Portal](https://portal.azure.com/)
2. Создайте новое приложение в Azure Active Directory
3. Добавьте платформу "Web" с Redirect URI: `http://localhost:3020/onedrive/redirect`
4. В API permissions добавьте Microsoft Graph > Delegated permissions:
   - `Files.Read`
   - `Files.ReadWrite`
   - `User.Read`
5. Скопируйте Application (client) ID и Client secret в `.env`

### 3. Запуск через Docker Compose

```bash
docker-compose up -d companion
```

### 4. Проверка работы

Откройте в браузере: `http://localhost:3020/`

Должен вернуться статус 200 OK.

### 5. Настройка фронтенда

Companion URL автоматически подхватывается из `window.COMPANION_URL` или можно указать вручную:

```javascript
const uppy = UppyManager.init({
    companionUrl: 'http://localhost:3020'
});
```

## Production настройки

Для production окружения:

1. **Измените COMPANION_SECRET** на случайную строку (минимум 32 символа)
2. **Настройте COMPANION_DOMAIN** на ваш реальный домен
3. **Используйте HTTPS** (COMPANION_PROTOCOL=https)
4. **Ограничьте COMPANION_ALLOWED_HOSTS** только вашими доменами
5. **Настройте правильные Redirect URIs** в OAuth приложениях для production домена

## Troubleshooting

### Companion не запускается

- Проверьте, что порт 3020 свободен
- Проверьте логи: `docker-compose logs companion`
- Убедитесь, что COMPANION_SECRET установлен

### OAuth не работает

- Проверьте, что Redirect URIs в OAuth приложениях совпадают с COMPANION_DOMAIN
- Убедитесь, что API включены в Google Cloud Console
- Проверьте, что ключи и секреты правильно скопированы в `.env`

### CORS ошибки

- Убедитесь, что COMPANION_ALLOWED_HOSTS содержит ваш фронтенд домен
- Проверьте, что CORS настроен правильно в FastAPI приложении

## Логи

Просмотр логов Companion:

```bash
docker-compose logs -f companion
```
