<?php

use App\Services\Engine\EngineErrorException;
use App\Services\Engine\EngineUnavailableException;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        $middleware->validateCsrfTokens(except: ['api/*']);
        // Delimiters such as "\t" or " " are legitimate values and must not be trimmed away.
        $middleware->trimStrings(except: ['import.ascii.delimiter', 'delimiter']);
        $middleware->convertEmptyStringsToNull(except: [
            fn (Request $request) => $request->is('api/projects/*/recordings'),
        ]);
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->shouldRenderJsonWhen(
            fn (Request $request) => $request->is('api/*') || $request->expectsJson(),
        );

        $exceptions->render(function (NotFoundHttpException $e, Request $request) {
            if ($request->is('api/*')) {
                $previous = $e->getPrevious();
                $message = $previous instanceof ModelNotFoundException
                    ? class_basename($previous->getModel()).' not found. It may have been deleted.'
                    : 'Not found.';

                return response()->json(['message' => $message], 404);
            }
        });

        $exceptions->render(function (EngineErrorException $e, Request $request) {
            $status = $e->status >= 400 && $e->status < 600 ? $e->status : 502;

            return response()->json([
                'message' => $e->getMessage(),
                'code' => $e->errorCode,
                'details' => $e->details,
            ], $status);
        });

        $exceptions->render(function (EngineUnavailableException $e, Request $request) {
            return response()->json([
                'message' => 'Processing engine is not running',
                'hint' => $e->getMessage(),
            ], 503);
        });
    })->create();
