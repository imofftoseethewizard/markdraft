(function () {
  'use strict';

  var app = document.getElementById('markdraft-app');
  var contentUrl = app.getAttribute('data-content-url');
  var refreshUrl = app.getAttribute('data-refresh-url');
  var theme = app.getAttribute('data-theme') || 'light';

  // Configure marked with highlight.js
  marked.setOptions({
    gfm: true,
    breaks: false,
    highlight: function (code, lang) {
      if (lang && typeof hljs !== 'undefined' && hljs.getLanguage(lang)) {
        try { return hljs.highlight(code, { language: lang }).value; }
        catch (e) { /* fall through */ }
      }
      if (typeof hljs !== 'undefined') {
        try { return hljs.highlightAuto(code).value; }
        catch (e) { /* fall through */ }
      }
      return code;
    }
  });

  // Custom renderer: mermaid code blocks become <pre class="mermaid">
  var renderer = new marked.Renderer();
  var origCode = renderer.code;
  renderer.code = function (code, language, escaped) {
    if (language === 'mermaid') {
      return '<pre class="mermaid">' + escapeHtml(code) + '</pre>';
    }
    if (origCode) {
      return origCode.call(this, code, language, escaped);
    }
    var esc = escapeHtml(code);
    if (language) {
      return '<pre><code class="hljs language-' + escapeHtml(language) + '">' + esc + '</code></pre>';
    }
    return '<pre><code>' + esc + '</code></pre>';
  };

  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function renderMarkdown(text) {
    var html = marked.parse(text, { renderer: renderer });
    document.getElementById('markdraft-content').innerHTML = html;
    initMermaid();
  }

  function fetchAndRender() {
    if (!contentUrl) return;
    fetch(contentUrl)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderMarkdown(data.text);
      })
      .catch(function (err) {
        document.getElementById('markdraft-content').innerHTML =
          '<p style="color:red">Error loading content: ' + escapeHtml(String(err)) + '</p>';
      });
  }

  function initMermaid() {
    if (typeof mermaid !== 'undefined') {
      try {
        mermaid.initialize({
          startOnLoad: false,
          theme: theme === 'dark' ? 'dark' : 'default'
        });
        mermaid.run({ querySelector: '.mermaid' });
      } catch (e) {
        // mermaid may not be loaded yet
      }
    }
  }

  function autorefresh(url) {
    var initialTitle = document.title;
    var source = new EventSource(url);
    var isRendering = false;

    source.onmessage = function (ev) {
      var msg = JSON.parse(ev.data);
      if (msg.updated) {
        isRendering = true;
        document.title = '(Rendering) ' + initialTitle;
        fetchAndRender();
        setTimeout(function () {
          isRendering = false;
          document.title = initialTitle;
        }, 200);
      }
    };

    source.onerror = function () {
      if (isRendering) {
        isRendering = false;
        document.title = initialTitle;
      }
    };
  }

  function scrollToHash() {
    if (location.hash && !document.querySelector(':target')) {
      var id = location.hash.slice(1);
      var el = document.getElementById(id) ||
               document.getElementById('user-content-' + id);
      if (el) el.scrollIntoView();
    }
  }

  // Boot
  var embedded = document.getElementById('markdraft-source');
  if (embedded) {
    renderMarkdown(embedded.textContent);
  } else {
    fetchAndRender();
  }

  if (refreshUrl) {
    autorefresh(refreshUrl);
  }

  window.onhashchange = scrollToHash;
  window.onload = scrollToHash;
})();
