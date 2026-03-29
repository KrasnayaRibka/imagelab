/**
 * Uppy Initialization Manager
 * @author Vadim Kalinin <vadimakalinin@gmail.com>
 * Encapsulates Uppy instance creation and event handling
 */
console.log('🔧 uppy-init.js загружен');

const UppyManager = {
    /**
     * Default configuration for Uppy instance
     */
    defaultConfig: {
        xhrEndpoint: '/imagelab/upload', // Use XHRUpload instead of TUS for form data support
        // Companion URL for cloud storage plugins (Dropbox, Google Drive, OneDrive, Google Photos)
        // If not set, cloud storage plugins will be disabled
        companionUrl: null, // Can be set via window.COMPANION_URL or in customConfig
        // Companion allowed hosts for OAuth security
        // If not set, defaults to companionUrl origin
        companionAllowedHosts: window.COMPANION_ALLOWED_HOSTS || null, // Can be set via window.COMPANION_ALLOWED_HOSTS or in customConfig
        restrictions: {
            maxFileSize: 350 * 1024 * 1024, // 350 MB
            maxNumberOfFiles: 300, // Maximum number of files that can be uploaded simultaneously
            // Validation is done by file extension only, not by MIME type
            allowedFileTypes: null // Allow all file types, validation by extension will be done in file-added handler
        },
        dashboard: {
            inline: true,
            target: '#uppy-dashboard',
        }
    },

    /**
     * Current Uppy instance
     */
    instance: null,

    /**
     * Get userID from input field
     * @returns {string|null} User ID value or null
     */
    getUserID: function() {
        const input = document.getElementById('userID-input');
        return input ? input.value : null;
    },
    getTestFormSecret: function() {
        if (typeof window !== 'undefined' && window.TEST_FORM_SEKRET) {
            return window.TEST_FORM_SEKRET;
        }
        const el = document.querySelector('[data-test-secret]');
        if (el && el.dataset.testSecret) {
            return el.dataset.testSecret;
        }
        return '';
    },

    /**
     * Initialize Uppy with custom or default configuration
     * @param {Object} customConfig - Custom configuration to override defaults
     * @returns {Object} Uppy instance
     */
    init: function(customConfig = {}) {
        // Normalize companionUrl - remove null, undefined, empty strings, and string "null"
        // First, get the value from customConfig or defaultConfig
        let companionUrl = customConfig.companionUrl !== undefined 
            ? customConfig.companionUrl 
            : (this.defaultConfig.companionUrl || null);
        
        console.log('🔍 [uppy-init] Исходный companionUrl:', {
            fromCustomConfig: customConfig.companionUrl,
            fromDefaultConfig: this.defaultConfig.companionUrl,
            selected: companionUrl,
            type: typeof companionUrl
        });
        
        // Clean up companionUrl value - convert invalid values to null
        if (companionUrl === null || 
            companionUrl === undefined || 
            companionUrl === '' || 
            companionUrl === 'null' || 
            companionUrl === 'undefined' ||
            (typeof companionUrl === 'string' && companionUrl.trim().length === 0)) {
            companionUrl = null;
        } else if (typeof companionUrl === 'string') {
            // Trim whitespace if it's a string
            companionUrl = companionUrl.trim();
        }
        
        console.log('🔍 [uppy-init] Нормализованный companionUrl:', companionUrl);
        
        // Get companionAllowedHosts from customConfig, defaultConfig, or window
        let companionAllowedHosts = customConfig.companionAllowedHosts !== undefined
            ? customConfig.companionAllowedHosts
            : (this.defaultConfig.companionAllowedHosts || null);
        
        // If companionAllowedHosts is not set and companionUrl is valid, derive from companionUrl
        if (companionAllowedHosts === null && companionUrl !== null) {
            try {
                const url = new URL(companionUrl);
                companionAllowedHosts = url.origin; // Use origin as default
            } catch (e) {
                // If URL parsing fails, leave as null
                companionAllowedHosts = null;
            }
        }
        
        // Build config - explicitly exclude companionUrl and companionAllowedHosts from spread
        // We'll add them separately after normalization to ensure they're valid
        const { companionUrl: _, companionAllowedHosts: __, ...defaultConfigWithoutCompanion } = this.defaultConfig;
        const { companionUrl: ___, companionAllowedHosts: ____, ...customConfigWithoutCompanion } = customConfig;
        
        const config = {
            ...defaultConfigWithoutCompanion,
            ...customConfigWithoutCompanion,
            restrictions: {
                ...this.defaultConfig.restrictions,
                ...(customConfig.restrictions || {})
            },
            dashboard: {
                ...this.defaultConfig.dashboard,
                ...(customConfig.dashboard || {})
            }
        };
        
        // CRITICAL: Only add companionUrl to config if it's valid (not null)
        // This prevents passing null/undefined to createUppyInstance
        // We explicitly set it here to ensure it's not lost during config merging
        if (companionUrl !== null && companionUrl !== undefined) {
            config.companionUrl = companionUrl;
            console.log('✅ companionUrl добавлен в config:', companionUrl);
        } else {
            console.warn('⚠️ companionUrl не добавлен в config (null или undefined):', companionUrl);
        }
        
        // Only add companionAllowedHosts if it's valid
        if (companionAllowedHosts !== null && companionAllowedHosts !== undefined) {
            config.companionAllowedHosts = companionAllowedHosts;
            console.log('✅ companionAllowedHosts добавлен в config:', companionAllowedHosts);
        } else {
            console.warn('⚠️ companionAllowedHosts не добавлен в config (null или undefined):', companionAllowedHosts);
        }

        // Configure XHRUpload plugin to include userID in form data
        // Use formData function to add userID to each file upload
        const self = this;
        config.xhr = {
            ...config.xhr,
            // Field name for the file (must match server expectation: 'file')
            fieldName: 'file',
            // Use formData function to add additional fields
            formData: (file) => {
                try {
                    console.log('🔧 XHRUpload formData функция ВЫЗВАНА для файла:', file.name);
                    
                    const userID = self.getUserID();
                    const testFormSecret = self.getTestFormSecret();
                    console.log('🔧 userID из input:', userID);
                    
                    const additionalFields = {};
                    
                    if (userID) {
                        additionalFields.userID = userID;
                        additionalFields.key = testFormSecret;
                        console.log('✅ userID добавлен в additionalFields:', additionalFields);
                    } else {
                        console.warn('⚠️ userID пустой!');
                    }
                    
                    // Log what we're adding to form data
                    console.log('🔧 XHRUpload formData возвращает:', additionalFields);
                    
                    // Return object with additional form fields
                    // XHRUpload will add these to FormData along with the file
                    return additionalFields;
                } catch (error) {
                    console.error('❌ ОШИБКА в функции formData:', error);
                    return {};
                }
            },
            getResponseData: (responseText, response) => {
                // Log what we receive
                console.log('📥 getResponseData вызвана с параметрами:', {
                    responseText: responseText,
                    response: response,
                    responseType: typeof response,
                    responseTextType: typeof responseText
                });
                
                // XHRUpload may pass response in different format
                // Check all possible response formats
                let status, statusText, headers;
                
                if (response) {
                    status = response.status || response.statusCode;
                    statusText = response.statusText;
                    headers = response.headers;
                }
                
                console.log('📥 Извлеченные данные ответа:', {
                    status: status,
                    statusText: statusText,
                    headers: headers
                });
                
                // Parse JSON response if available
                let parsedData;
                try {
                    if (responseText && typeof responseText === 'string') {
                        parsedData = JSON.parse(responseText);
                        console.log('📥 Ответ от сервера (parsed):', parsedData);
                    } else if (responseText && typeof responseText === 'object') {
                        // Already parsed
                        parsedData = responseText;
                        console.log('📥 Ответ от сервера (уже объект):', parsedData);
                    } else {
                        console.warn('⚠️ responseText пустой или неожиданного типа');
                        parsedData = {};
                    }
                } catch (e) {
                    console.warn('⚠️ Не удалось распарсить JSON:', e);
                    parsedData = responseText || {};
                }
                // Return data in format expected by Uppy
                // Uppy expects the response body data
                return parsedData;
            },
            bundle: false,
            ...(customConfig.xhr || {})
        };

        // Log companionUrl status for debugging
        const companionUrlStatus = config.companionUrl 
            ? `настроен: ${config.companionUrl}` 
            : 'не настроен (облачные плагины отключены)';
        
        const companionAllowedHostsStatus = config.companionAllowedHosts
            ? `настроен: ${config.companionAllowedHosts}`
            : 'не настроен (будет использован origin из companionUrl)';
        
        console.log('🔧 Инициализация Uppy с конфигурацией:', {
            xhrEndpoint: config.xhrEndpoint,
            companionUrl: companionUrlStatus,
            companionAllowedHosts: companionAllowedHostsStatus,
            companionUrlType: typeof config.companionUrl,
            companionUrlValue: config.companionUrl,
            companionAllowedHostsValue: config.companionAllowedHosts,
            xhr: config.xhr
        });
        
        // Check if createUppyInstance is available
        if (typeof createUppyInstance !== 'function') {
            console.error('❌ ОШИБКА: createUppyInstance не найдена! Убедитесь, что uppy-bundle.js загружен перед uppy-init.js');
            return null;
        }

        // Log final config before passing to createUppyInstance
        console.log('🔍 [uppy-init] Финальный config перед передачей в createUppyInstance:', {
            companionUrl: config.companionUrl,
            companionAllowedHosts: config.companionAllowedHosts,
            hasCompanionUrl: config.companionUrl !== undefined && config.companionUrl !== null,
            hasCompanionAllowedHosts: config.companionAllowedHosts !== undefined && config.companionAllowedHosts !== null
        });

        this.instance = createUppyInstance(config);
        console.log('✅ Uppy instance создан:', this.instance);
        
        // File extension validation - only check extensions, ignore MIME types
        const allowedExtensions = ['jpg', 'jpeg', 'png', 'gif', 'tif', 'psd', 'zip', 'heic', 'dng'];
        
        // Validate files by extension only (MIME types are ignored)
        this.instance.on('file-added', (file) => {
            const fileName = file.name || '';
            const fileExt = fileName.split('.').pop()?.toLowerCase();
            
            // Validate extension - this is the only check we do
            if (!fileExt || !allowedExtensions.includes(fileExt)) {
                const allowedStr = allowedExtensions.join(', ');
                this.instance.removeFile(file.id);
                this.instance.info({
                    message: `Файл "${fileName}" имеет недопустимое расширение. Разрешенные расширения: ${allowedStr}`,
                    details: `Расширение "${fileExt}" не разрешено.`
                }, 'error', 5000);
                console.warn(`⚠️ Файл "${fileName}" отклонен: расширение "${fileExt}" не разрешено`);
            } else {
                console.log(`✅ Файл "${fileName}" принят с расширением "${fileExt}" (MIME тип: "${file.type || 'неизвестен'}" - игнорируется)`);
            }
        });
        
        
        // Add interceptor to log actual request being sent
        this.instance.on('upload', () => {
            console.log('🔍 Проверка конфигурации XHRUpload:');
            const xhrPlugin = this.instance.getPlugin('XHRUpload');
            if (xhrPlugin) {
                console.log('✅ XHRUpload plugin найден:', xhrPlugin);
                console.log('🔍 Конфигурация XHRUpload:', {
                    endpoint: xhrPlugin.opts.endpoint,
                    fieldName: xhrPlugin.opts.fieldName,
                    formData: typeof xhrPlugin.opts.formData,
                    method: xhrPlugin.opts.method,
                    formDataValue: xhrPlugin.opts.formData
                });
                
                // Try to call formData function manually to test
                const files = this.instance.getFiles();
                if (files.length > 0 && typeof xhrPlugin.opts.formData === 'function') {
                    console.log('🧪 Тестируем вызов formData функции...');
                    try {
                        const testResult = xhrPlugin.opts.formData(files[0]);
                        console.log('✅ formData функция вызвана успешно, результат:', testResult);
                    } catch (error) {
                        console.error('❌ ОШИБКА при вызове formData функции:', error);
                    }
                }
            } else {
                console.error('❌ XHRUpload plugin не найден!');
            }
        });
        
        this.setupEventHandlers();
        
        return this.instance;
    },

    /**
     * Setup event handlers for Uppy instance
     */
    setupEventHandlers: function() {
        if (!this.instance) {
            console.error('Uppy instance is not initialized');
            return;
        }

        // Set userID in file metadata before upload starts
        // XHRUpload automatically includes metadata in FormData
        this.instance.on('upload', () => {
            const userID = this.getUserID();
            const testFormSecret = this.getTestFormSecret();
            
            // Check if userID is provided
            if (!userID) {
                console.warn('⚠️ ВНИМАНИЕ: userID не указан! Пожалуйста, введите User ID перед загрузкой.');
            }
            
            // Get files from Uppy instance
            const files = this.instance.getFiles();
            
            if (!files || files.length === 0) {
                console.warn('⚠️ Нет файлов для загрузки');
                return;
            }
            
            // Set userID metadata for all files
            files.forEach(file => {
                // Set userID in file metadata - XHRUpload will include it in FormData
                this.instance.setFileMeta(file.id, {
                    userID: userID,
                    key: testFormSecret,
                    ...(file.meta || {})
                });
            });
            
            console.log('🚀 Начало загрузки:', {
                userID: userID,
                files: files.map(f => ({
                    id: f.id,
                    name: f.name,
                    size: f.size,
                    type: f.type,
                    meta: this.instance.getFile(f.id)?.meta
                }))
            });
            
            // Log what will be sent to server
            console.log('📤 Данные для отправки на сервер:', {
                endpoint: this.defaultConfig.xhrEndpoint || '/imagelab/upload',
                files: files.map(f => {
                    const fileObj = this.instance.getFile(f.id);
                    const fileMeta = fileObj?.meta || {};
                    return {
                        fileName: f.name,
                        fileSize: f.size,
                        fileType: f.type,
                        formData: {
                            file: f.name,
                            userID: fileMeta.userID || userID,
                            key: testFormSecret,
                            ...fileMeta
                        }
                    };
                })
            });
        });

        // Log upload progress
        this.instance.on('upload-progress', (file, progress) => {
            console.log(`⏳ Прогресс загрузки [${file.name}]:`, {
                bytesUploaded: progress.bytesUploaded,
                bytesTotal: progress.bytesTotal,
                percentage: Math.round((progress.bytesUploaded / progress.bytesTotal) * 100) + '%'
            });
        });

        // Log successful upload
        this.instance.on('upload-success', (file, response) => {
            console.log('✅ Загрузка успешна:', {
                fileName: file.name,
                response: response
            });
            
            // Log RabbitMQ response if available
            if (response && response.rabbitmq_response) {
                const rabbitmqResponse = response.rabbitmq_response;
                if (rabbitmqResponse.status === 'ok' || rabbitmqResponse.status === 'success') {
                    console.log('✅ RabbitMQ ответ (save_image):', rabbitmqResponse);
                } else {
                    console.error('❌ RabbitMQ ошибка (save_image):', rabbitmqResponse);
                }
            } else if (response && response.image_data) {
                // If response structure is different, try to find rabbitmq_response
                console.warn('⚠️ RabbitMQ ответ не найден в структуре response');
            }
        });

        // Log when all uploads complete
        this.instance.on('complete', (result) => {
            console.log('✅ Все загрузки завершены:', {
                successful: result.successful,
                failed: result.failed,
                total: result.successful.length + result.failed.length
            });
            console.log('✅ Успешные загрузки:', result.successful);
            if (result.failed.length > 0) {
                console.error('❌ Ошибки загрузки:', result.failed);
            }
        });

        // Log upload errors
        this.instance.on('upload-error', (file, error, response) => {
            console.error('❌ Ошибка загрузки:', {
                fileName: file.name,
                error: error,
                response: response,
                errorMessage: error?.message,
                errorStack: error?.stack
            });
        });
        
        // Log any errors
        this.instance.on('error', (error) => {
            console.error('❌ Общая ошибка Uppy:', error);
        });
        
        // Log when upload starts (before XHRUpload processes)
        this.instance.on('upload', () => {
            console.log('🚀 Событие upload сработало');
        });

        // Hide time remaining indicator in StatusBar using CSS and DOM manipulation
        // This hides elements containing "Осталось" text while keeping other progress indicators
        const hideTimeRemaining = () => {
            const statusBar = document.querySelector('.uppy-StatusBar');
            if (!statusBar) return;

            // Find all statusSecondary elements and hide those containing "Осталось"
            const statusSecondaryElements = statusBar.querySelectorAll('.uppy-StatusBar-statusSecondary');
            statusSecondaryElements.forEach(element => {
                if (element.textContent && element.textContent.includes('Осталось')) {
                    element.style.display = 'none';
                }
            });
        };

        // Hide time remaining immediately
        setTimeout(hideTimeRemaining, 100);
        
        // Use MutationObserver to hide time remaining when StatusBar updates
        const observer = new MutationObserver(() => {
            hideTimeRemaining();
        });

        // Observe changes in document for StatusBar creation and updates
        const docObserver = new MutationObserver(() => {
            const statusBar = document.querySelector('.uppy-StatusBar');
            if (statusBar) {
                hideTimeRemaining();
                observer.observe(statusBar, {
                    childList: true,
                    subtree: true,
                    characterData: true
                });
            }
        });

        docObserver.observe(document.body, {
            childList: true,
            subtree: true
        });
    },

    /**
     * Get current Uppy instance
     * @returns {Object|null} Current Uppy instance or null
     */
    getInstance: function() {
        return this.instance;
    },

    /**
     * Destroy current Uppy instance
     */
    destroy: function() {
        if (this.instance) {
            this.instance.close();
            this.instance = null;
        }
    }
};

