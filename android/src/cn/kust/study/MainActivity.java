package cn.kust.study;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.*;
import android.widget.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

public class MainActivity extends Activity {
  private static final String BASE="https://news.kongfu.xyz/kust/";
  private static final String OFFLINE="https://appassets.androidplatform.net/kust/";
  private WebView web;
  private byte[] exportBytes;
  private boolean offline=false;
  private boolean pageReady=false;
  @Override public void onCreate(Bundle b){
    super.onCreate(b);
    getWindow().setStatusBarColor(Color.rgb(250,250,250));
    getWindow().setNavigationBarColor(Color.WHITE);
    getWindow().getDecorView().setSystemUiVisibility(android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|android.view.View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
    web=new WebView(this);setContentView(web);
    WebSettings s=web.getSettings();s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);s.setAllowFileAccess(false);s.setAllowContentAccess(false);s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);s.setUserAgentString(s.getUserAgentString()+" KustAndroid/1.0.4");
    CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
    web.setWebChromeClient(new WebChromeClient());
    web.setWebViewClient(new WebViewClient(){
      @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){
        Uri u=r.getUrl();
        if(!"appassets.androidplatform.net".equals(u.getHost()))return null;
        String p=u.getPath();if(p==null||!p.startsWith("/kust/")||p.contains(".."))return missing();
        p=p.substring(6);if(p.isEmpty())p="index.html";
        String mime=p.endsWith(".css")?"text/css":p.endsWith(".js")?"text/javascript":p.endsWith(".json")?"application/json":p.endsWith(".svg")?"image/svg+xml":p.endsWith(".webp")?"image/webp":p.endsWith(".png")?"image/png":p.endsWith(".jpg")||p.endsWith(".jpeg")?"image/jpeg":p.endsWith(".gif")?"image/gif":p.endsWith(".ttf")?"font/ttf":"text/html";
        try{return new WebResourceResponse(mime,"UTF-8",getAssets().open("site/"+p));}catch(IOException e){return missing();}
      }
      @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){return route(r.getUrl());}
      @Override public void onReceivedError(WebView v,WebResourceRequest r,WebResourceError e){
        if(r.isForMainFrame()&&!offline){offline=true;v.loadUrl(OFFLINE);Toast.makeText(MainActivity.this,"网络暂不可用，已打开随包题库。原卷需要联网查看。",Toast.LENGTH_LONG).show();}
      }
      @Override public void onPageFinished(WebView v,String u){
        pageReady=true;
        if(offline)v.evaluateJavascript("if(document.querySelector('.intro-note'))document.querySelector('.intro-note').textContent='离线题库 · 重新打开应用可连接服务器';document.querySelectorAll('.app-link').forEach(e=>e.style.display='none')",null);
        else v.evaluateJavascript("document.querySelectorAll('.app-link').forEach(e=>e.style.display='none')",null);
      }
    });
    web.setDownloadListener((url,ua,disposition,mime,length)->route(Uri.parse(url)));
    web.loadUrl(BASE);
    new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(()->{if(!pageReady&&!offline){offline=true;web.stopLoading();web.loadUrl(OFFLINE);Toast.makeText(this,"已打开离线题库，原卷需联网查看。",Toast.LENGTH_LONG).show();}},12000);
  }
  private WebResourceResponse missing(){return new WebResourceResponse("text/plain","UTF-8",404,"Not found",null,new ByteArrayInputStream(new byte[0]));}
  private boolean route(Uri uri){
    String scheme=uri.getScheme();
    if("kust-export".equals(scheme)){
      String data=uri.getQueryParameter("data");if(data==null||data.length()>5000000)return true;
      exportBytes=data.getBytes(StandardCharsets.UTF_8);
      Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT);i.addCategory(Intent.CATEGORY_OPENABLE);i.setType("application/json");i.putExtra(Intent.EXTRA_TITLE,"昆工拾题-学习记录.json");
      try{startActivityForResult(i,42);}catch(Exception e){Toast.makeText(this,"无法打开文件保存器",Toast.LENGTH_LONG).show();}return true;
    }
    if(!"https".equals(scheme)&&!"http".equals(scheme))return true;
    String url=uri.toString();
    if(url.startsWith(OFFLINE+"files/")||url.startsWith(OFFLINE+"original-files/")||url.startsWith(OFFLINE+"downloads/"))url=BASE+url.substring(OFFLINE.length());
    if((url.equals(BASE)||url.equals(BASE+"index.html")||url.equals(BASE+"originals.html"))&&!offline)return false;
    if(url.equals(OFFLINE)||url.equals(OFFLINE+"index.html")||url.equals(OFFLINE+"originals.html"))return false;
    try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(url)));}catch(Exception e){new AlertDialog.Builder(this).setMessage("请使用浏览器打开："+url).setPositiveButton("知道了",null).show();}return true;
  }
  @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==42&&result==RESULT_OK&&data!=null&&data.getData()!=null&&exportBytes!=null){try(OutputStream out=getContentResolver().openOutputStream(data.getData())){out.write(exportBytes);Toast.makeText(this,"学习记录已保存",Toast.LENGTH_SHORT).show();}catch(Exception e){Toast.makeText(this,"保存失败，请重试",Toast.LENGTH_LONG).show();}}exportBytes=null;}
  @Override public void onBackPressed(){web.evaluateJavascript("(function(){var ds=document.querySelectorAll('dialog[open]');var d=ds[ds.length-1];if(d){d.close();return true;}return false;})()",value->{if(!"true".equals(value)){if(web.canGoBack())web.goBack();else finish();}});}
  @Override protected void onDestroy(){web.destroy();super.onDestroy();}
}
