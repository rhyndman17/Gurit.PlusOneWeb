USE [HMNZL]
GO

SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

IF OBJECT_ID(N'[dbo].[hmlPlusOneAppLock]', N'U') IS NULL
BEGIN
    CREATE TABLE [dbo].[hmlPlusOneAppLock](
        [AppName] [varchar](50) NOT NULL,
        [LockID] [uniqueidentifier] NOT NULL,
        [Site] [varchar](10) NOT NULL,
        [UserName] [varchar](128) NOT NULL,
        [MachineName] [varchar](128) NOT NULL,
        [AcquiredDateTime] [datetime] NOT NULL,
        [LastHeartbeatDateTime] [datetime] NOT NULL,
        CONSTRAINT [PK_hmlPlusOneAppLock] PRIMARY KEY CLUSTERED ([AppName] ASC)
    ) ON [PRIMARY]
END
GO
