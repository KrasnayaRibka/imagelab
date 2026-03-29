# Быстрая настройка Companion сервера

## Шаг 1: Добавьте переменные в .env

Добавьте в ваш `.env` файл следующие переменные:

```env
# Обязательные настройки Companion
COMPANION_SECRET=your-random-secret-min-32-chars
COMPANION_DOMAIN=localhost:3020
COMPANION_PROTOCOL=http
COMPANION_ALLOWED_HOSTS=http://localhost:8000,http://localhost:3020

# Опционально: OAuth ключи для облачных провайдеров
# Google Drive & Photos
COMPANION_GOOGLE_KEY=
COMPANION_GOOGLE_SECRET=

# Dropbox
COMPANION_DROPBOX_KEY=
COMPANION_DROPBOX_SECRET=

# OneDrive
COMPANION_ONEDRIVE_KEY=
COMPANION_ONEDRIVE_SECRET=
```

**Важно:** Сгенерируйте случайный `COMPANION_SECRET`:
```bash
node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"
```

## Шаг 2: Запустите Companion

```bash
docker-compose up -d companion
```

## Шаг 3: Проверьте работу

Откройте в браузере: `http://localhost:3020/`

Должен вернуться статус 200 OK.

## Шаг 4: Настройте фронтенд (опционально)

Companion URL автоматически подхватывается. Если нужно указать вручную:

```javascript
// В вашем HTML или JS файле
window.COMPANION_URL = 'http://localhost:3020';
```

Или в `uppy-init.js`:

```javascript
const uppy = UppyManager.init({
    companionUrl: 'http://localhost:3020'
});
```

## Готово! 🎉

Теперь в Uppy Dashboard будут доступны кнопки:
- ✅ **Camera** - работает сразу
- ✅ **Link** - работает сразу  
- ⚠️ **Dropbox** - нужны OAuth ключи
- ⚠️ **OneDrive** - нужны OAuth ключи
- ⚠️ **Google Drive** - нужны OAuth ключи
- ⚠️ **Google Photos** - нужны OAuth ключи

## Получение OAuth ключей

См. подробные инструкции в `companion/README.md`

## Просмотр логов

```bash
docker-compose logs -f companion
```
