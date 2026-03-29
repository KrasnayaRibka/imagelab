/**
 * Uppy bundle entry point
 * 
 * This file imports and initializes Uppy with the required plugins:
 * - @uppy/core - Core Uppy functionality
 * - @uppy/dashboard - Dashboard UI
 * - @uppy/tus - TUS resumable upload plugin
 * - @uppy/xhr-upload - XHR upload plugin for standard POST requests
 * - @uppy/webcam - Camera plugin for taking photos
 * - @uppy/url - URL plugin for importing files from URLs
 * - @uppy/dropbox - Dropbox plugin (requires Companion server)
 * - @uppy/onedrive - OneDrive plugin (requires Companion server)
 * - @uppy/google-drive - Google Drive plugin (requires Companion server)
 * - @uppy/google-photos-picker - Google Photos plugin (requires Companion server)
 * 
 * Note: Drag and drop is handled by Dashboard's built-in functionality
 * and custom window event handlers to prevent browser from opening files
 * 
 * Author: Vadim Kalinin
 * Email: vadimakalin@gmail.com
 */

import Uppy from '@uppy/core';
import Dashboard from '@uppy/dashboard';
import Tus from '@uppy/tus';
import XHRUpload from '@uppy/xhr-upload';
import Webcam from '@uppy/webcam';
import Url from '@uppy/url';
import Dropbox from '@uppy/dropbox';
import OneDrive from '@uppy/onedrive';
import GoogleDrive from '@uppy/google-drive';
import GooglePhotosPicker from '@uppy/google-photos-picker';

// Russian locale for Uppy Dashboard
const ru_RU = {
    strings: {
        // Dashboard strings
        closeModal: 'Закрыть',
        addMoreFiles: 'Добавить ещё файлы',
        addingMoreFiles: 'Добавление файлов',
        importFrom: 'Импорт из %{name}',
        dashboardWindowTitle: 'Окно Uppy Dashboard (Нажмите Escape для закрытия)',
        dashboardTitle: 'Uppy Dashboard',
        copyLinkToClipboardSuccess: 'Ссылка скопирована в буфер обмена.',
        copyLinkToClipboardFallback: 'Скопируйте URL ниже',
        copyLink: 'Копировать ссылку',
        back: 'Назад',
        removeFile: 'Удалить файл',
        editFile: 'Редактировать файл',
        editImage: 'Редактировать изображение',
        editing: 'Редактирование %{file}',
        error: 'Ошибка',
        finishEditingFile: 'Завершить редактирование',
        saveChanges: 'Сохранить изменения',
        myDevice: 'Моё устройство',
        camera: 'Камера',
        dropHint: 'Перетащите файлы сюда',
        uploadComplete: 'Загрузка завершена',
        uploadPaused: 'Загрузка приостановлена',
        resumeUpload: 'Возобновить загрузку',
        pauseUpload: 'Приостановить загрузку',
        retryUpload: 'Повторить загрузку',
        cancelUpload: 'Отменить загрузку',
        xFilesSelected: {
            0: 'Выбран %{smart_count} файл',
            1: 'Выбрано %{smart_count} файла',
            2: 'Выбрано %{smart_count} файлов',
        },
        uploadingXFiles: {
            0: 'Загрузка %{smart_count} файла',
            1: 'Загрузка %{smart_count} файлов',
            2: 'Загрузка %{smart_count} файлов',
        },
        processingXFiles: {
            0: 'Обработка %{smart_count} файла',
            1: 'Обработка %{smart_count} файлов',
            2: 'Обработка %{smart_count} файлов',
        },
        poweredBy: 'Работает на %{uppy}',
        addMore: 'Добавить ещё',
        editFileWithFilename: 'Редактировать файл %{file}',
        save: 'Сохранить',
        cancel: 'Отмена',
        dropPasteFiles: 'Перетащите файлы сюда или %{browseFiles}',
        dropPasteFolders: 'Перетащите файлы сюда или %{browseFolders}',
        dropPasteBoth: 'Перетащите файлы сюда, %{browseFiles} или %{browseFolders}',
        dropPasteImportFiles: 'Перетащите файлы сюда, %{browseFiles} или импортируйте из:',
        dropPasteImportFolders: 'Перетащите файлы сюда, %{browseFolders} или импортируйте из:',
        dropPasteImportBoth: 'Перетащите файлы сюда, %{browseFiles}, %{browseFolders} или импортируйте из:',
        importFiles: 'Импортировать файлы из:',
        browseFiles: 'выберите файлы',
        browseFolders: 'выбрать папки',
        recoveredXFiles: {
            0: 'Не удалось полностью восстановить 1 файл. Пожалуйста, выберите его снова и возобновите загрузку.',
            1: 'Не удалось полностью восстановить %{smart_count} файла. Пожалуйста, выберите их снова и возобновите загрузку.',
            2: 'Не удалось полностью восстановить %{smart_count} файлов. Пожалуйста, выберите их снова и возобновите загрузку.',
        },
        recoveredAllFiles: 'Все файлы восстановлены. Теперь вы можете возобновить загрузку.',
        sessionRestored: 'Сессия восстановлена',
        reSelect: 'Выбрать снова',
        missingRequiredMetaFields: {
            0: 'Отсутствует обязательное поле: %{fields}.',
            1: 'Отсутствуют обязательные поля: %{fields}.',
            2: 'Отсутствуют обязательные поля: %{fields}.',
        },
        takePictureBtn: 'Сделать фото',
        recordVideoBtn: 'Записать видео',
        // StatusBar strings
        uploading: 'Загрузка',
        complete: 'Завершено',
        uploadFailed: 'Загрузка не удалась',
        paused: 'Приостановлено',
        retry: 'Повторить',
        pause: 'Приостановить',
        resume: 'Возобновить',
        done: 'Готово',
        filesUploadedOfTotal: {
            0: '%{complete} из %{smart_count} файла загружено',
            1: '%{complete} из %{smart_count} файлов загружено',
            2: '%{complete} из %{smart_count} файлов загружено',
        },
        dataUploadedOfTotal: '%{complete} из %{total}',
        dataUploadedOfUnknown: '%{complete} из неизвестного',
        xTimeLeft: 'Осталось %{time}',
        uploadXFiles: {
            0: 'Загрузить %{smart_count} файл',
            1: 'Загрузить %{smart_count} файла',
            2: 'Загрузить %{smart_count} файлов',
        },
        uploadXNewFiles: {
            0: 'Загрузить +%{smart_count} файл',
            1: 'Загрузить +%{smart_count} файла',
            2: 'Загрузить +%{smart_count} файлов',
        },
        upload: 'Загрузить',
        xMoreFilesAdded: {
            0: 'Добавлен ещё %{smart_count} файл',
            1: 'Добавлено ещё %{smart_count} файла',
            2: 'Добавлено ещё %{smart_count} файлов',
        },
        showErrorDetails: 'Показать детали ошибки',
        // Core strings
        addBulkFilesFailed: {
            0: 'Не удалось добавить %{smart_count} файл из-за внутренней ошибки',
            1: 'Не удалось добавить %{smart_count} файла из-за внутренних ошибок',
            2: 'Не удалось добавить %{smart_count} файлов из-за внутренних ошибок',
        },
        youCanOnlyUploadX: {
            0: 'Вы можете загрузить только %{smart_count} файл',
            1: 'Вы можете загрузить только %{smart_count} файла',
            2: 'Вы можете загрузить только %{smart_count} файлов',
        },
        youHaveToAtLeastSelectX: {
            0: 'Вы должны выбрать хотя бы %{smart_count} файл',
            1: 'Вы должны выбрать хотя бы %{smart_count} файла',
            2: 'Вы должны выбрать хотя бы %{smart_count} файлов',
        },
        aggregateExceedsSize: 'Вы выбрали %{size} файлов, но максимально допустимый размер составляет %{sizeAllowed}',
        exceedsSize: '%{file} превышает максимально допустимый размер %{size}',
        missingRequiredMetaField: 'Отсутствуют обязательные поля',
        missingRequiredMetaFieldOnFile: 'Отсутствуют обязательные поля в %{fileName}',
        inferiorSize: 'Этот файл меньше допустимого размера %{size}',
        youCanOnlyUploadFileTypes: 'Вы можете загрузить только: %{types}',
        noMoreFilesAllowed: 'Нельзя добавить больше файлов',
        noDuplicates: 'Нельзя добавить дубликат файла "%{fileName}", он уже существует',
        companionError: 'Ошибка подключения к Companion',
        authAborted: 'Аутентификация прервана',
        companionUnauthorizeHint: 'Чтобы отменить авторизацию вашего аккаунта %{provider}, перейдите на %{url}',
        failedToUpload: 'Не удалось загрузить %{file}',
        noInternetConnection: 'Нет подключения к Интернету',
        connectedToInternet: 'Подключено к Интернету',
        noFilesFound: 'Здесь нет файлов или папок',
        noSearchResults: 'К сожалению, нет результатов для этого поиска',
        selectX: {
            0: 'Выбрать %{smart_count}',
            1: 'Выбрать %{smart_count}',
            2: 'Выбрать %{smart_count}',
        },
        allFilesFromFolderNamed: 'Все файлы из папки %{name}',
        openFolderNamed: 'Открыть папку %{name}',
        logOut: 'Выйти',
        logIn: 'Войти',
        pickFiles: 'Выберите файлы',
        pickPhotos: 'Выбрать фото',
        filter: 'Фильтр',
        resetFilter: 'Сбросить фильтр',
        loading: 'Загрузка...',
        loadedXFiles: 'Загружено %{numFiles} файлов',
        authenticateWithTitle: 'Пожалуйста, выполните аутентификацию с %{pluginName} для выбора файлов',
        authenticateWith: 'Подключиться к %{pluginName}',
        signInWithGoogle: 'Войти через Google',
        searchImages: 'Поиск изображений',
        enterTextToSearch: 'Введите текст для поиска изображений',
        search: 'Поиск',
        resetSearch: 'Сбросить поиск',
        emptyFolderAdded: 'Из пустой папки не было добавлено файлов',
        addedNumFiles: 'Добавлено %{numFiles} файл(ов)',
        folderAlreadyAdded: 'Папка "%{folder}" уже была добавлена',
        folderAdded: {
            0: 'Добавлен %{smart_count} файл из %{folder}',
            1: 'Добавлено %{smart_count} файла из %{folder}',
            2: 'Добавлено %{smart_count} файлов из %{folder}',
        },
        additionalRestrictionsFailed: '%{count} дополнительных ограничений не выполнено',
        unnamed: 'Без названия',
        pleaseWait: 'Пожалуйста, подождите',
    },
};

// Export Uppy and plugins for use in HTML
window.Uppy = Uppy;
window.UppyDashboard = Dashboard;
window.UppyTus = Tus;
window.UppyXHRUpload = XHRUpload;
window.UppyWebcam = Webcam;
window.UppyUrl = Url;
window.UppyDropbox = Dropbox;
window.UppyOneDrive = OneDrive;
window.UppyGoogleDrive = GoogleDrive;
window.UppyGooglePhotosPicker = GooglePhotosPicker;

// Export a helper function to create a configured Uppy instance
window.createUppyInstance = function(options = {}) {
    const defaultOptions = {
        id: 'uppy',
        locale: ru_RU, // Set Russian locale for Core
        restrictions: {
            maxFileSize: null, // No limit by default
            maxNumberOfFiles: null, // No limit by default
            allowedFileTypes: ['image/*'] // Only images by default
        },
        ...options
    };

    const uppy = new Uppy(defaultOptions);

    // Add Dashboard plugin with Russian locale
    // Ensure disableLocalFiles is false to allow drag and drop
    uppy.use(Dashboard, {
        inline: true,
        target: '#uppy-dashboard',
        showProgressDetails: true,
        proudlyDisplayPoweredByUppy: false,
        locale: ru_RU,
        disableLocalFiles: false, // Enable local file selection and drag-drop
        ...(options.dashboard || {})
    });

    // Setup global drag and drop handlers to intercept ALL drag-and-drop events
    // and add files to Uppy regardless of where they are dropped
    // Completely prevent browser's default drag-and-drop behavior
    // Use capture phase to intercept events before Dashboard can handle them
    if (typeof window !== 'undefined' && typeof document !== 'undefined') {
        if (!window.__uppyDragDropHandlersInstalled) {
            const handleDragOver = (e) => {
                // Always prevent default to stop browser from opening files
                e.preventDefault();
                // Always stop propagation to prevent Dashboard from handling it
                e.stopPropagation();
            };

            const handleDragEnter = (e) => {
                // Prevent default to stop browser from opening files
                e.preventDefault();
                // Stop propagation to prevent Dashboard from handling it
                e.stopPropagation();
            };

            const handleDragLeave = (e) => {
                // Prevent default
                e.preventDefault();
                // Stop propagation
                e.stopPropagation();
            };

            const handleDrop = (e) => {
                // Always prevent browser's default behavior (opening files)
                e.preventDefault();
                // Always stop propagation to prevent Dashboard from handling it
                e.stopPropagation();
                
                // Get files from the drop event
                const files = e.dataTransfer?.files;
                if (files && files.length > 0) {
                    console.log('📥 [uppy-bundle] Drop detected, adding files to Uppy:', files.length);
                    
                    // Try to find Uppy instance - it should be stored in window or accessible via UppyManager
                    let uppyInstance = null;
                    
                    // Try to get from UppyManager if available
                    if (typeof window.UppyManager !== 'undefined' && window.UppyManager.getInstance) {
                        uppyInstance = window.UppyManager.getInstance();
                    }
                    
                    // If not found, try to get from global variable
                    if (!uppyInstance && window.__currentUppyInstance) {
                        uppyInstance = window.__currentUppyInstance;
                    }
                    
                    if (uppyInstance) {
                        // Convert FileList to Array and add to Uppy
                        Array.from(files).forEach(file => {
                            try {
                                uppyInstance.addFile({
                                    name: file.name,
                                    type: file.type,
                                    data: file,
                                    source: 'Local',
                                    isRemote: false
                                });
                                console.log('✅ [uppy-bundle] File added to Uppy:', file.name);
                            } catch (error) {
                                console.error('❌ [uppy-bundle] Error adding file to Uppy:', error, file.name);
                            }
                        });
                    } else {
                        console.warn('⚠️ [uppy-bundle] Uppy instance not found, cannot add files');
                    }
                }
            };

            // Add event listeners in CAPTURE phase (true) to intercept events before Dashboard
            // This ensures we handle ALL drag-and-drop events first
            window.addEventListener('dragover', handleDragOver, true);
            window.addEventListener('dragenter', handleDragEnter, true);
            window.addEventListener('dragleave', handleDragLeave, true);
            window.addEventListener('drop', handleDrop, true);
            
            // Also add to document to catch events that might not bubble to window
            document.addEventListener('dragover', handleDragOver, true);
            document.addEventListener('dragenter', handleDragEnter, true);
            document.addEventListener('dragleave', handleDragLeave, true);
            document.addEventListener('drop', handleDrop, true);
            
            window.__uppyDragDropHandlersInstalled = true;
            console.log('✅ [uppy-bundle] Global drag-drop handlers installed (capture phase)');
        }
        
        // Store reference to this Uppy instance for use in global handlers
        window.__currentUppyInstance = uppy;
    }

    // Add Webcam plugin for camera access
    // Set modes to ['picture'] to disable video recording button
    const webcamOptions = {
        target: Dashboard,
        modes: ['picture'], // Only allow photo capture, disable video recording
        ...(options.webcam || {})
    };
    webcamOptions.locale = {
        ...(options.webcam && options.webcam.locale ? options.webcam.locale : {}),
        strings: {
            pluginNameCamera: 'Камера',
            ...((options.webcam && options.webcam.locale && options.webcam.locale.strings) ? options.webcam.locale.strings : {})
        }
    };
    uppy.use(Webcam, webcamOptions);

    // Add cloud storage plugins (require Companion server)
    // These plugins will only work if companionUrl is configured
    // IMPORTANT: Do not add these plugins if companionUrl is null, undefined, or invalid
    // to prevent "Companion hostname is required" errors
    // NOTE: URL plugin also requires companionUrl, so it will be added together with cloud storage plugins
    
    const companionUrl = options.companionUrl;
    
    console.log('🔍 [uppy-bundle] createUppyInstance вызван с options:', {
        companionUrl: options.companionUrl,
        companionAllowedHosts: options.companionAllowedHosts,
        hasCompanionUrl: options.companionUrl !== undefined && options.companionUrl !== null,
        companionUrlType: typeof options.companionUrl,
        companionUrlValue: options.companionUrl
    });
    
    // Strict validation: companionUrl must be a valid non-empty string
    // Check explicitly for null, undefined, empty strings, and string representations of null/undefined
    let hasCompanionUrl = false;
    
    if (companionUrl !== null && 
        companionUrl !== undefined && 
        typeof companionUrl === 'string') {
        const trimmed = companionUrl.trim();
        if (trimmed.length > 0 && 
            trimmed !== 'null' && 
            trimmed !== 'undefined' &&
            trimmed.toLowerCase() !== 'null' &&
            trimmed.toLowerCase() !== 'undefined') {
            hasCompanionUrl = true;
        }
    }
    
    // Only add cloud storage plugins if companionUrl is valid
    // If hasCompanionUrl is false, these plugins will NOT be added at all
    // This prevents "Companion hostname is required" errors
    if (hasCompanionUrl) {
        const validCompanionUrl = companionUrl.trim();
        
        // Double-check that validCompanionUrl is actually valid
        if (!validCompanionUrl || validCompanionUrl.length === 0) {
            console.error('❌ [uppy-bundle] КРИТИЧЕСКАЯ ОШИБКА: validCompanionUrl пустой после trim()!', {
                originalCompanionUrl: companionUrl,
                trimmedCompanionUrl: validCompanionUrl,
                hasCompanionUrl: hasCompanionUrl
            });
            throw new Error('validCompanionUrl is empty after trim()');
        }
        
        console.log('✅ [uppy-bundle] companionUrl валиден, добавляем плагины облачных хранилищ:', validCompanionUrl);
        console.log('🔍 [uppy-bundle] Детали валидации:', {
            originalCompanionUrl: companionUrl,
            trimmedCompanionUrl: validCompanionUrl,
            hasCompanionUrl: hasCompanionUrl,
            companionUrlType: typeof validCompanionUrl,
            companionUrlLength: validCompanionUrl.length
        });
        
        // Get companionAllowedHosts from options
        // If not provided, default to companionUrl origin for security
        let companionAllowedHosts = options.companionAllowedHosts;
        if (!companionAllowedHosts) {
            try {
                const url = new URL(validCompanionUrl);
                companionAllowedHosts = url.origin; // Default to origin of companionUrl
                console.log('✅ [uppy-bundle] companionAllowedHosts установлен из companionUrl origin:', companionAllowedHosts);
            } catch (e) {
                // If URL parsing fails, use companionUrl as fallback
                companionAllowedHosts = validCompanionUrl;
                console.warn('⚠️ [uppy-bundle] Не удалось распарсить companionUrl, используем как fallback:', companionAllowedHosts);
            }
        } else {
            console.log('✅ [uppy-bundle] companionAllowedHosts из options:', companionAllowedHosts);
        }
        
        // Helper function to merge plugin options while ensuring companionUrl and companionAllowedHosts are valid
        // This ensures that companionUrl is always set to a valid value, even if plugin options override it
        const mergePluginOptions = (pluginOptions, pluginName) => {
            const merged = { ...(pluginOptions || {}) };
            // CRITICAL: Always override companionUrl with our validated value
            // This prevents passing null/undefined from plugin-specific options
            merged.companionUrl = validCompanionUrl;
            // Also ensure companionAllowedHosts is set
            merged.companionAllowedHosts = companionAllowedHosts;
            // Remove any invalid companionUrl values that might be in plugin options
            if (merged.companionUrl === null || merged.companionUrl === undefined) {
                merged.companionUrl = validCompanionUrl;
            }
            return merged;
        };
        
        try {
            // Add URL plugin for importing files from URLs
            // URL plugin also requires companionUrl, so it must be added here
            // CRITICAL: Set companionUrl and companionAllowedHosts AFTER spread to ensure they're never overwritten
            const urlOptions = {
                target: Dashboard,
                ...(options.url || {}),
                companionUrl: validCompanionUrl, // Explicitly set companionUrl LAST to ensure it's never overwritten
                companionAllowedHosts: companionAllowedHosts // Set companionAllowedHosts LAST for OAuth security
            };
            
            // Double-check that companionUrl is set correctly
            if (!urlOptions.companionUrl || urlOptions.companionUrl === null || urlOptions.companionUrl === undefined) {
                console.error('❌ [uppy-bundle] КРИТИЧЕСКАЯ ОШИБКА: companionUrl не установлен в urlOptions!', {
                    validCompanionUrl: validCompanionUrl,
                    urlOptions: urlOptions,
                    optionsUrl: options.url
                });
                throw new Error('companionUrl is required for Url plugin but was not set correctly');
            }
            
            console.log('🔍 [uppy-bundle] Добавляем Url с опциями:', {
                companionUrl: urlOptions.companionUrl,
                companionAllowedHosts: urlOptions.companionAllowedHosts,
                hasCompanionUrl: urlOptions.companionUrl !== undefined && urlOptions.companionUrl !== null,
                companionUrlType: typeof urlOptions.companionUrl,
                companionUrlValue: urlOptions.companionUrl
            });
            uppy.use(Url, urlOptions);

            // Add Dropbox plugin
            // CRITICAL: Set companionUrl and companionAllowedHosts AFTER spread to ensure they're never overwritten
            const dropboxOptions = {
                target: Dashboard,
                ...mergePluginOptions(options.dropbox, 'Dropbox'),
                companionUrl: validCompanionUrl, // Explicitly set companionUrl LAST to ensure it's never overwritten
                companionAllowedHosts: companionAllowedHosts // Set companionAllowedHosts LAST for OAuth security
            };
            console.log('🔍 [uppy-bundle] Добавляем Dropbox с опциями:', {
                companionUrl: dropboxOptions.companionUrl,
                companionAllowedHosts: dropboxOptions.companionAllowedHosts,
                hasCompanionUrl: dropboxOptions.companionUrl !== undefined && dropboxOptions.companionUrl !== null
            });
            uppy.use(Dropbox, dropboxOptions);

            // Add OneDrive plugin
            const onedriveOptions = {
                target: Dashboard,
                ...mergePluginOptions(options.onedrive, 'OneDrive'),
                companionUrl: validCompanionUrl,
                companionAllowedHosts: companionAllowedHosts
            };
            console.log('🔍 [uppy-bundle] Добавляем OneDrive с опциями:', {
                companionUrl: onedriveOptions.companionUrl,
                companionAllowedHosts: onedriveOptions.companionAllowedHosts
            });
            uppy.use(OneDrive, onedriveOptions);

            // Add Google Drive plugin
            const googleDriveOptions = {
                target: Dashboard,
                ...mergePluginOptions(options.googleDrive, 'GoogleDrive'),
                companionUrl: validCompanionUrl,
                companionAllowedHosts: companionAllowedHosts
            };
            console.log('🔍 [uppy-bundle] Добавляем GoogleDrive с опциями:', {
                companionUrl: googleDriveOptions.companionUrl,
                companionAllowedHosts: googleDriveOptions.companionAllowedHosts
            });
            uppy.use(GoogleDrive, googleDriveOptions);

            // Add Google Photos Picker plugin
            const googlePhotosOptions = {
                target: Dashboard,
                ...mergePluginOptions(options.googlePhotosPicker, 'GooglePhotosPicker'),
                companionUrl: validCompanionUrl,
                companionAllowedHosts: companionAllowedHosts
            };
            console.log('🔍 [uppy-bundle] Добавляем GooglePhotosPicker с опциями:', {
                companionUrl: googlePhotosOptions.companionUrl,
                companionAllowedHosts: googlePhotosOptions.companionAllowedHosts
            });
            uppy.use(GooglePhotosPicker, googlePhotosOptions);
        } catch (error) {
            console.error('❌ Ошибка при добавлении плагинов облачных хранилищ:', error);
            // Don't throw - just log the error and continue without cloud storage plugins
        }
    } else {
        // Log that cloud storage plugins and URL plugin are disabled
        console.log('ℹ️ [uppy-bundle] Плагины облачных хранилищ и URL плагин отключены: companionUrl не настроен или невалиден', {
            companionUrl: companionUrl,
            companionUrlType: typeof companionUrl,
            companionUrlValue: companionUrl,
            note: 'URL плагин также требует companionUrl для работы'
        });
    }
    // If companionUrl is not valid, cloud storage plugins are simply not added
    // No error will be thrown - they just won't be available

    // Add upload plugin - prefer XHRUpload if xhrEndpoint is provided, otherwise use TUS
    if (options.xhrEndpoint) {
        // Use XHRUpload for standard POST requests with form data support
        // formData can be a function that returns additional form fields
        const xhrConfig = {
            endpoint: options.xhrEndpoint,  // <-- ENDPOINT задается здесь
            method: 'post',
            fieldName: 'file',
            ...(options.xhr || {})
        };
        
        // Set formData: if it's a function in options.xhr, use it; otherwise use true
        // When formData is a function, XHRUpload will call it for each file and add returned fields to FormData
        if (options.xhr && typeof options.xhr.formData === 'function') {
            xhrConfig.formData = options.xhr.formData;  // Function to add additional form fields
        } else if (options.xhr && options.xhr.formData !== undefined) {
            xhrConfig.formData = options.xhr.formData;  // Use explicit value (true/false)
        } else {
            xhrConfig.formData = true;  // Use FormData by default
        }
        
        uppy.use(XHRUpload, xhrConfig);
    } else if (options.tusEndpoint) {
        // Use TUS plugin for resumable uploads
        uppy.use(Tus, {
            endpoint: options.tusEndpoint,
            retryDelays: [0, 1000, 3000, 5000],
            ...(options.tus || {})
        });
    }

    return uppy;
};

