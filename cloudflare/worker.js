/**
 * Cloudflare Worker: HomeWorker (Telegram Mini App Reverse Proxy & CDN)
 *
 * Связка Alwaysdata + Cloudflare Workers:
 * 1. Проксирует запросы /api/* на ваш сервер Alwaysdata с автоматическим CORS.
 * 2. Проксирует раздачу статики (index.html, style.css, app.js) с сервера Alwaysdata.
 * 3. Обеспечивает постоянный, бесплатный и быстрый HTTPS URL для Telegram BotFather и Mini App.
 */

// Укажите адрес вашего сервера на Alwaysdata (можно также задать в переменных Worker: ALWAYSDATA_BACKEND_URL)
const DEFAULT_ALWAYSDATA_URL = "https://leronfu.alwaysdata.net";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const backendBase = (env?.ALWAYSDATA_BACKEND_URL || DEFAULT_ALWAYSDATA_URL).replace(/\/+$/, "");
    const backendHost = new URL(backendBase).host;

    // 1. Обработка CORS Pre-flight (OPTIONS)
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Telegram-Init-Data, X-Dev-Telegram-Id",
          "Access-Control-Max-Age": "86400",
        },
      });
    }

    // 2. Формируем целевой URL на Alwaysdata
    const targetUrl = new URL(url.pathname + url.search, backendBase);

    // Копируем и модифицируем заголовки
    const newHeaders = new Headers(request.headers);
    newHeaders.set("Host", backendHost);
    newHeaders.set("X-Forwarded-Host", url.host);
    newHeaders.set("X-Forwarded-Proto", "https");

    try {
      const response = await fetch(targetUrl.toString(), {
        method: request.method,
        headers: newHeaders,
        body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
        redirect: "follow",
      });

      // Добавляем CORS-заголовки к ответу
      const responseHeaders = new Headers(response.headers);
      responseHeaders.set("Access-Control-Allow-Origin", "*");
      responseHeaders.set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");

      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: responseHeaders,
      });
    } catch (err) {
      return new Response(
        JSON.stringify({
          error: "Ошибка подключения к серверу Alwaysdata",
          details: err.message,
          backend: backendBase,
        }),
        {
          status: 502,
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
          },
        }
      );
    }
  },
};
