USE [msdb]
GO

/*
    Creates a SQL Server Agent job to run the PlusOne extract/upload wrapper.

    Review these values before running:
      - @installFolder: folder containing Run-ExtractUpload.ps1, PlusOneWeb.exe, and PlusOneConfig.json
      - @activeStartTime: 24-hour HHMMSS schedule time
      - @sites: 'NZ,AU', 'NZ', or 'AU'
*/

DECLARE @jobName sysname = N'PlusOne Extract Upload';
DECLARE @scheduleName sysname = N'PlusOne Extract Upload - Daily';
DECLARE @installFolder nvarchar(4000) = N'C:\Program Files (x86)\Microsoft Dynamics\PlusOne';
DECLARE @activeStartTime int = 230000; -- 11:00 PM
DECLARE @sites nvarchar(20) = N'NZ,AU';
DECLARE @command nvarchar(max);

SET @command =
    N'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& ''' +
    @installFolder +
    N'\Run-ExtractUpload.ps1'' -Sites ' +
    @sites +
    N' -KeepGoing"';

IF EXISTS (SELECT 1 FROM msdb.dbo.sysjobs WHERE [name] = @jobName)
BEGIN
    EXEC msdb.dbo.sp_delete_job @job_name = @jobName, @delete_unused_schedule = 1;
END

EXEC msdb.dbo.sp_add_job
    @job_name = @jobName,
    @enabled = 1,
    @description = N'Runs PlusOne extract then upload using Run-ExtractUpload.ps1.',
    @category_name = N'[Uncategorized (Local)]';

EXEC msdb.dbo.sp_add_jobstep
    @job_name = @jobName,
    @step_name = N'Run extract/upload',
    @subsystem = N'CmdExec',
    @command = @command,
    @cmdexec_success_code = 0,
    @on_success_action = 1,
    @on_fail_action = 2,
    @retry_attempts = 0,
    @retry_interval = 0;

EXEC msdb.dbo.sp_add_schedule
    @schedule_name = @scheduleName,
    @enabled = 1,
    @freq_type = 4, -- daily
    @freq_interval = 1,
    @active_start_time = @activeStartTime;

EXEC msdb.dbo.sp_attach_schedule
    @job_name = @jobName,
    @schedule_name = @scheduleName;

EXEC msdb.dbo.sp_add_jobserver
    @job_name = @jobName,
    @server_name = N'(LOCAL)';
GO
