# Uppy Bundle для imagelab

Этот bundle содержит настроенный Uppy с модулями:
- `@uppy/core` - Основная функциональность Uppy
- `@uppy/dashboard` - UI Dashboard для загрузки файлов
- `@uppy/tus` - Плагин для возобновляемой загрузки через TUS протокол

## Установка зависимостей

```bash
npm install
```

## Сборка

### Production сборка (минифицированная)
```bash
npm run build
```

### Development сборка (с sourcemap)
```bash
npm run build:dev
```

### Watch режим (автоматическая пересборка при изменениях)
```bash
npm run watch
```

## Использование в HTML

После сборки файл `dist/uppy-bundle.js` можно подключить к HTML:

```html
<!DOCTYPE html>
<html>
<head>
    <link href="https://releases.transloadit.com/uppy/v3.0.0/uppy.min.css" rel="stylesheet">
</head>
<body>
    <div id="uppy-dashboard"></div>
    
    <script src="/static/uppy-bundle.js"></script>
    <script>
        const uppy = createUppyInstance({
            tusEndpoint: '/upload',
            restrictions: {
                maxFileSize: 10 * 1024 * 1024, // 10 MB
                allowedFileTypes: ['image/*']
            },
            dashboard: {
                inline: true,
                target: '#uppy-dashboard'
            }
        });

        uppy.on('complete', (result) => {
            console.log('Upload complete!', result);
        });
    </script>
</body>
</html>
```

## API

### `createUppyInstance(options)`

Создает и настраивает экземпляр Uppy.

**Параметры:**
- `options.tusEndpoint` (string) - URL endpoint для TUS загрузки
- `options.restrictions` (object) - Ограничения на файлы
- `options.dashboard` (object) - Настройки Dashboard
- `options.tus` (object) - Дополнительные настройки TUS плагина

**Возвращает:** Настроенный экземпляр Uppy

