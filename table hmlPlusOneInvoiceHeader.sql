
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE TABLE [dbo].[hmlPlusOneInvoiceHeader](
    [InvoiceHeaderID] [int] IDENTITY(1,1) NOT NULL,
    [ImportBatchID] [uniqueidentifier] NOT NULL,
    [SupplierID] [char](15) NOT NULL,
    [DocumentDate] [datetime] NULL,
    [AccountingValueDate] [datetime] NULL,
    [DocumentNo] [char](21) NOT NULL,
    [ImageURL] [char](200) NULL,
    [Status] [int] NOT NULL,
    [Processed] [datetime] NULL,
    [FileName] [char](200) NOT NULL,
    [GPVoucherNumber] [char](17) NULL,
    [GPBatchID] [char](15) NULL,
    [HeaderMessage] [varchar](max) NULL,
    [CreatedDateTime] [datetime] NOT NULL,
    [LastUpdatedDateTime] [datetime] NOT NULL,
 CONSTRAINT [PK_hmlPlusOneInvoiceHeader] PRIMARY KEY CLUSTERED
(
    [InvoiceHeaderID] ASC
) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

ALTER TABLE [dbo].[hmlPlusOneInvoiceHeader] ADD CONSTRAINT [DF_hmlPlusOneInvoiceHeader_ImportBatchID] DEFAULT (newid()) FOR [ImportBatchID]
GO

ALTER TABLE [dbo].[hmlPlusOneInvoiceHeader] ADD CONSTRAINT [DF_hmlPlusOneInvoiceHeader_Status] DEFAULT ((0)) FOR [Status]
GO

ALTER TABLE [dbo].[hmlPlusOneInvoiceHeader] ADD CONSTRAINT [DF_hmlPlusOneInvoiceHeader_CreatedDateTime] DEFAULT (getdate()) FOR [CreatedDateTime]
GO

ALTER TABLE [dbo].[hmlPlusOneInvoiceHeader] ADD CONSTRAINT [DF_hmlPlusOneInvoiceHeader_LastUpdatedDateTime] DEFAULT (getdate()) FOR [LastUpdatedDateTime]
GO

CREATE UNIQUE NONCLUSTERED INDEX [UX_hmlPlusOneInvoiceHeader_ImportBatchDocument]
ON [dbo].[hmlPlusOneInvoiceHeader]([ImportBatchID] ASC, [SupplierID] ASC, [DocumentNo] ASC)
GO

CREATE NONCLUSTERED INDEX [IX_hmlPlusOneInvoiceHeader_Status]
ON [dbo].[hmlPlusOneInvoiceHeader]([Status] ASC, [Processed] ASC, [DocumentDate] ASC)
GO

CREATE NONCLUSTERED INDEX [IX_hmlPlusOneInvoiceHeader_SupplierDocument]
ON [dbo].[hmlPlusOneInvoiceHeader]([SupplierID] ASC, [DocumentNo] ASC)
INCLUDE ([Status], [Processed], [FileName])
GO
