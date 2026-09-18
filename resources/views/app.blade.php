<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="app-version" content="{{ config('hvsr.app_version') }}">
    <meta name="color-scheme" content="light dark">
    <title>QuakeLogic HVSR Studio</title>
    <link rel="icon" href="/favicon.ico" sizes="any">
    <script>
        (function () {
            try {
                var theme = localStorage.getItem('hvsr-theme') || 'system';
                var dark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
                if (dark) document.documentElement.classList.add('dark');
            } catch (e) {}
        })();
    </script>
    @vite(['resources/css/app.css', 'resources/js/app.ts'])
</head>
<body class="h-full antialiased">
    <div id="app"></div>
</body>
</html>
