/**
 * MultiUserUploadRunner handles concurrent upload simulation.
 * Author: Vadim Kalinin
 * Email: vadimakalin@gmail.com
 */
class MultiUserUploadRunner {
  constructor(options) {
    this.endpoint = options.endpoint;
    this.secretKey = options.secretKey;
    this.defaultUserId = options.defaultUserId;
    this.logEl = options.logEl;
    this.statusEl = options.statusEl;
    this.reportEl = options.reportEl;
    this.texts = options.texts;
  }

  log(message) {
    const timestamp = new Date().toISOString();
    this.logEl.value += `[${timestamp}] ${message}\n`;
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  setStatus(message) {
    this.statusEl.textContent = message;
  }

  setReport(text) {
    this.reportEl.textContent = text;
  }

  formatTemplate(template, values) {
    return template.replace(/\{(\w+)\}/g, (match, key) => {
      return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : match;
    });
  }

  parseUserIds(rawIds, usersCount) {
    const trimmed = rawIds.trim();
    if (trimmed.length === 0) {
      const count = Number.isFinite(usersCount) && usersCount > 0 ? usersCount : 1;
      return new Array(count).fill(this.defaultUserId);
    }
    const parts = trimmed
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    const ids = parts
      .map((value) => parseInt(value, 10))
      .filter((value) => Number.isFinite(value));
    return ids.length > 0 ? ids : [this.defaultUserId];
  }

  async uploadFileForUser(file, userId) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("userID", String(userId));
    formData.append("key", this.secretKey);

    const response = await fetch(this.endpoint, {
      method: "POST",
      body: formData,
    });
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, status: response.status, data };
  }

  async run(files, userIds) {
    const tasks = [];
    const reportData = new Map();
    const ensureUser = (userId) => {
      if (!reportData.has(userId)) {
        reportData.set(userId, {
          files: [],
          totalSizeKb: 0,
          totalTimeSec: 0,
        });
      }
      return reportData.get(userId);
    };
    const formatKb = (kb) => kb.toFixed(2);
    const formatSec = (sec) => sec.toFixed(2);
    const recordReport = (userId, file, elapsedMs, status) => {
      const entry = ensureUser(userId);
      const sizeKb = file.size / 1024;
      const timeSec = elapsedMs / 1000;
      entry.files.push({
        name: file.name,
        status: status,
        sizeKb: sizeKb,
        timeSec: timeSec,
      });
      entry.totalSizeKb += sizeKb;
      entry.totalTimeSec += timeSec;
    };

    for (const userId of userIds) {
      for (const file of files) {
        const label = `user=${userId}, file=${file.name}`;
        this.log(`Queued: ${label}`);
        const startTime = performance.now();
        tasks.push(
          this.uploadFileForUser(file, userId)
            .then((result) => {
              const elapsedMs = performance.now() - startTime;
              const status = result.ok
                ? this.texts.statusOk
                : `${this.texts.statusError} ${result.status}`;
              recordReport(userId, file, elapsedMs, status);
              this.log(`Done: ${label}, status=${result.status}`);
              return result;
            })
            .catch((error) => {
              const elapsedMs = performance.now() - startTime;
              recordReport(userId, file, elapsedMs, this.texts.statusError);
              this.log(`Failed: ${label}, error=${error.message}`);
              return { ok: false, status: 0, data: { error: error.message } };
            })
        );
      }
    }
    const statusRunning = this.formatTemplate(this.texts.statusRunning, {
      count: tasks.length,
    });
    this.setStatus(statusRunning);
    const results = await Promise.all(tasks);
    const successCount = results.filter((item) => item.ok).length;
    const failureCount = results.length - successCount;
    const statusCompleted = this.formatTemplate(this.texts.statusCompleted, {
      success: successCount,
      failed: failureCount,
    });
    this.setStatus(statusCompleted);
    const reportLines = [];
    const userIdCounts = new Map();
    for (const userId of userIds) {
      userIdCounts.set(userId, (userIdCounts.get(userId) || 0) + 1);
    }
    const userIdSeen = new Map();
    for (const userId of userIds) {
      if (!reportData.has(userId)) {
        continue;
      }
      const data = reportData.get(userId);
      const totalCount = userIdCounts.get(userId) || 0;
      const seenCount = (userIdSeen.get(userId) || 0) + 1;
      userIdSeen.set(userId, seenCount);
      const suffix = totalCount > 1 ? `/${seenCount}` : "";
      reportLines.push(`${this.texts.reportUserId} (${userId}):${suffix}`);
      for (const fileEntry of data.files) {
        reportLines.push(
          this.formatTemplate(this.texts.reportFileFormat, {
            name: fileEntry.name,
            size_kb: formatKb(fileEntry.sizeKb),
            time_sec: formatSec(fileEntry.timeSec),
            status: fileEntry.status,
          })
        );
      }
      reportLines.push(
        this.formatTemplate(this.texts.reportTotalFormat, {
          size_kb: formatKb(data.totalSizeKb),
          time_sec: formatSec(data.totalTimeSec),
        })
      );
      reportLines.push("");
    }
    this.setReport(reportLines.join("\n").trim());
  }
}

const DEFAULT_USER_ID = 26;
const texts = {
  statusNoFiles: document.body.dataset.statusNoFiles || "Выберите хотя бы один файл.",
  statusRunning: document.body.dataset.statusRunning || "Выполняется {count} запросов...",
  statusCompleted:
    document.body.dataset.statusCompleted || "Готово. Успешно: {success}, Ошибок: {failed}",
  reportUserId: document.body.dataset.reportUserId || "User ID",
  reportFileFormat:
    document.body.dataset.reportFileFormat ||
    "Файл {name}: размер {size_kb} кб, загружался {time_sec} сек, статус {status}.",
  reportTotalFormat:
    document.body.dataset.reportTotalFormat ||
    "Вся загрузка пользователя: {size_kb} кб, {time_sec} сек.",
  statusOk: document.body.dataset.statusOk || "успешно",
  statusError: document.body.dataset.statusError || "ошибка",
};
const testSecret = document.body.dataset.testSecret || "";
const runner = new MultiUserUploadRunner({
  endpoint: "/imagelab/upload",
  secretKey: testSecret,
  defaultUserId: DEFAULT_USER_ID,
  logEl: document.getElementById("log"),
  statusEl: document.getElementById("status"),
  reportEl: document.getElementById("report"),
  texts: texts,
});

document.getElementById("start-btn").addEventListener("click", () => {
  const filesInput = document.getElementById("file-input");
  const usersCountInput = document.getElementById("users-count-input");
  const userIdsInput = document.getElementById("user-ids-input");

  const files = Array.from(filesInput.files || []);
  if (files.length === 0) {
    runner.setStatus(texts.statusNoFiles);
    return;
  }

  const usersCount = parseInt(usersCountInput.value, 10);
  const userIds = runner.parseUserIds(userIdsInput.value, usersCount);
  runner.log(`Start upload: users=${userIds.join(", ")}, files=${files.length}`);
  runner.run(files, userIds);
});

document.getElementById("clear-btn").addEventListener("click", () => {
  runner.logEl.value = "";
  runner.setStatus("");
  runner.setReport("");
});
