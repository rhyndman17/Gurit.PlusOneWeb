SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE TABLE [dbo].[hmlPlusOneMessages](
	[MessageDateTime] [datetime] NULL,
	[DetailDesc1] [char](100) NULL,
	[DetailDesc2] [char](100) NULL,
	[MessageID] [char](10) NULL,
	[MessageState] [int] NULL,
	[MessageString1] [char](255) NULL,
	[MessageString2] [char](255) NULL
) ON [PRIMARY]
GO


