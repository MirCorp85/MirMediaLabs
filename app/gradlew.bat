@rem Gradle wrapper startup script for Windows
@if "%DEBUG%"=="" @echo off
@rem Set local scope for variables
setlocal

set DIRNAME=%~dp0
if "%DIRNAME%"=="" set DIRNAME=.
@rem Set JAVA_HOME if not set
if not defined JAVA_HOME set JAVA_HOME=C:\Program Files\Java\jdk-21.0.10

set JAVA_EXE=%JAVA_HOME%\bin\java.exe
if not exist "%JAVA_EXE%" (
    echo ERROR: JAVA_HOME is set incorrectly. Cannot find java.exe at: %JAVA_EXE%
    goto fail
)

set CLASSPATH=%DIRNAME%gradle\wrapper\gradle-wrapper.jar
"%JAVA_EXE%" -classpath "%CLASSPATH%" org.gradle.wrapper.GradleWrapperMain %*

:fail
exit /b 1
