package com.party.dj

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.view.Gravity
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject

/**
 * The phone app: runs the same Python party DJ as the Mac inside the app, then shows the
 * DJ page full screen. The screen stays on so the music never stops mid-party.
 */
class MainActivity : Activity() {
    private val ui = Handler(Looper.getMainLooper())
    private lateinit var status: TextView
    private var web: WebView? = null
    private var speech: SpeechRecognizer? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        showLoading()
        val missing = arrayOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.CAMERA)
            .filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) requestPermissions(missing.toTypedArray(), 1)

        if (!Python.isStarted()) Python.start(AndroidPlatform(this))
        val dir = filesDir.absolutePath
        Thread { Python.getInstance().getModule("partydj.phone").callAttr("start", dir) }.start()
        ui.post(::poll)
    }

    private fun showLoading() {
        status = TextView(this).apply {
            setTextColor(Color.WHITE); textSize = 18f; gravity = Gravity.CENTER; setPadding(48, 32, 48, 0)
            text = "Starting the DJ…"
        }
        val title = TextView(this).apply {
            setTextColor(Color.parseColor("#FF2D7A")); textSize = 26f; gravity = Gravity.CENTER
            text = "🎧 Ketan's Birthday Party DJ"
        }
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER
            setBackgroundColor(Color.parseColor("#0D0D12"))
            addView(title); addView(ProgressBar(this@MainActivity).apply { setPadding(0, 48, 0, 0) }); addView(status)
        })
    }

    private fun poll() {
        val s = JSONObject(Python.getInstance().getModule("partydj.phone").callAttr("status").toString())
        when {
            !s.isNull("error") -> status.text =
                "Something went wrong:\n${s.getString("error")}\n\nCheck the internet connection, then close and reopen the app."
            s.getBoolean("ready") -> showDj(s.getString("url"))
            else -> { status.text = s.getString("text"); ui.postDelayed(::poll, 500) }
        }
    }

    private fun showDj(url: String) {
        val view = WebView(this)
        view.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
        }
        view.webViewClient = WebViewClient()
        view.webChromeClient = object : WebChromeClient() {
            // The crowd camera on the DJ page (it only works out a movement number).
            override fun onPermissionRequest(request: PermissionRequest) {
                val local = request.origin.host == "localhost" || request.origin.host == "127.0.0.1"
                if (local) request.grant(request.resources) else request.deny()
            }
        }
        view.addJavascriptInterface(SpeechBridge(), "AndroidSpeech")
        view.loadUrl(url)
        web = view
        setContentView(view)
    }

    /** The 🎙 Speak button: the phone's own speech recogniser, since web views don't have one. */
    inner class SpeechBridge {
        @JavascriptInterface
        fun listen() = ui.post {
            if (!SpeechRecognizer.isRecognitionAvailable(this@MainActivity)) {
                reply(null); return@post
            }
            speech?.destroy()
            speech = SpeechRecognizer.createSpeechRecognizer(this@MainActivity).apply {
                setRecognitionListener(object : RecognitionListener {
                    override fun onResults(results: Bundle) {
                        reply(results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull())
                    }
                    override fun onError(error: Int) = reply(null)
                    override fun onReadyForSpeech(params: Bundle?) {}
                    override fun onBeginningOfSpeech() {}
                    override fun onRmsChanged(rmsdB: Float) {}
                    override fun onBufferReceived(buffer: ByteArray?) {}
                    override fun onEndOfSpeech() {}
                    override fun onPartialResults(partialResults: Bundle?) {}
                    override fun onEvent(eventType: Int, params: Bundle?) {}
                })
                startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-IN")
                })
            }
        }
    }

    private fun reply(text: String?) {
        val arg = if (text == null) "null" else JSONObject.quote(text)
        web?.evaluateJavascript("window.onAndroidSpeech && window.onAndroidSpeech($arg)", null)
    }

    @Deprecated("Back would stop the party, so ask first")
    override fun onBackPressed() {
        AlertDialog.Builder(this)
            .setMessage("End the party? The music will stop.")
            .setPositiveButton("End party") { _, _ -> finishAndRemoveTask(); android.os.Process.killProcess(android.os.Process.myPid()) }
            .setNegativeButton("Keep playing", null)
            .show()
    }

    override fun onDestroy() {
        speech?.destroy()
        super.onDestroy()
    }
}
