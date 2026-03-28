package com.example.telehealth_app

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.os.Bundle
import android.view.KeyEvent
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.ProgressBar
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView

    // Deployed WHO Triage Portal URL (Vercel)
    private val PORTAL_URL = "https://telehealth-portal-ruby.vercel.app"

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)

        // ── WebView settings ──────────────────────────────────
        webView.settings.apply {
            javaScriptEnabled      = true   // Required for React app execution
            domStorageEnabled      = true   // Enables localStorage (keeps login session)
            loadWithOverviewMode   = true   // Fit page to screen width
            useWideViewPort        = true   // Use desktop viewport
            setSupportZoom(true)            // Enable pinch-to-zoom
            builtInZoomControls    = true
            displayZoomControls    = false  // Hide zoom buttons (pinch only)
            cacheMode = WebSettings.LOAD_DEFAULT
            mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
        }

        // ── WebViewClient: open all links inside the app ──────
        webView.webViewClient = object : WebViewClient() {

            // Called when a page starts loading
            override fun onPageStarted(view: WebView, url: String, favicon: Bitmap?) {
                super.onPageStarted(view, url, favicon)
            }

            // Called when a page finishes loading
            override fun onPageFinished(view: WebView, url: String) {
                super.onPageFinished(view, url)
            }

            // External links (tel:, mailto:, etc.) are handed off to the system
            override fun shouldOverrideUrlLoading(
                view: WebView,
                request: WebResourceRequest
            ): Boolean {
                val url = request.url.toString()
                return if (url.startsWith("http://") || url.startsWith("https://")) {
                    false   // Handle inside WebView
                } else {
                    // Delegate non-web schemes to the default system app
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                    true
                }
            }
        }

        // ── WebChromeClient: handles JS dialogs and console ───
        webView.webChromeClient = WebChromeClient()

        // ── Load portal URL ───────────────────────────────────
        // Restore previous page on activity recreation (e.g. screen rotation)
        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState)
        } else {
            webView.loadUrl(PORTAL_URL)
        }
    }

    // ── Save WebView state on activity recreation ─────────────
    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        webView.saveState(outState)
    }

    // ── Back button: navigate web history instead of closing app
    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView.canGoBack()) {
            webView.goBack()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }
}
