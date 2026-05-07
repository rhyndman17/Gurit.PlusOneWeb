
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE TABLE [dbo].[hmlPlusOneInvoiceLine](
    [InvoiceLineID] [int] IDENTITY(1,1) NOT NULL,
    [InvoiceHeaderID] [int] NULL,
    [ImportBatchID] [uniqueidentifier] NOT NULL,
    [SourceLineNo] [int] NOT NULL,
    [GLDimension1] [char](20) NULL,
    [GLDimension2] [char](20) NULL,
    [SupplierID] [char](15) NOT NULL,
    [DocumentDate] [datetime] NULL,
    [AccountingValueDate] [datetime] NULL,
    [DocumentNo] [char](21) NOT NULL,
    [ImageURL] [char](200) NULL,
    [FileName] [char](200) NOT NULL,
    [LedgerCode] [char](50) NULL,
    [LineValueExclGST] [numeric](18, 2) NULL,
    [LineValueGST] [numeric](18, 2) NULL,
    [UnitValueExclGST] [numeric](18, 2) NULL,
    [UnitValueGST] [numeric](18, 2) NULL,
    [LineDescription] [char](30) NULL,
    [PurchaseOrderNo] [char](20) NULL,
    [POLine] [int] NULL,
    [InvoicedQty] [numeric](18, 5) NULL,
    [GLDimension3] [char](50) NULL,
    [Status] [int] NOT NULL,
    [Processed] [datetime] NULL,
    [ErrorState] [int] NULL,
    [LineMessage] [varchar](max) NULL,
    [CreatedDateTime] [datetime] NOT NULL,
    [LastUpdatedDateTime] [datetime] NOT NULL,
 CONSTRAINT [PK_hmlPlusOneInvoiceLine] PRIMARY KEY CLUSTERED
(
    [InvoiceLineID] ASC
) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

ALTER TABLE [dbo].[hmlPlusOneInvoiceLine] ADD CONSTRAINT [DF_hmlPlusOneInvoiceLine_ImportBatchID] DEFAULT (newid()) FOR [ImportBatchID]
GO

ALTER TABLE [dbo].[hmlPlusOneInvoiceLine] ADD CONSTRAINT [DF_hmlPlusOneInvoiceLine_UnitValueExclGST] DEFAULT ((0)) FOR [UnitValueExclGST]
GO

ALTER TABLE [dbo].[hmlPlusOneInvoiceLine] ADD CONSTRAINT [DF_hmlPlusOneInvoiceLine_UnitValueGST] DEFAULT ((0)) FOR [UnitValueGST]
GO

ALTER TABLE [dbo].[hmlPlusOneInvoiceLine] ADD CONSTRAINT [DF_hmlPlusOneInvoiceLine_Status] DEFAULT ((0)) FOR [Status]
GO

ALTER TABLE [dbo].[hmlPlusOneInvoiceLine] ADD CONSTRAINT [DF_hmlPlusOneInvoiceLine_CreatedDateTime] DEFAULT (getdate()) FOR [CreatedDateTime]
GO

ALTER TABLE [dbo].[hmlPlusOneInvoiceLine] ADD CONSTRAINT [DF_hmlPlusOneInvoiceLine_LastUpdatedDateTime] DEFAULT (getdate()) FOR [LastUpdatedDateTime]
GO

ALTER TABLE [dbo].[hmlPlusOneInvoiceLine]  WITH CHECK ADD  CONSTRAINT [FK_hmlPlusOneInvoiceLine_Header]
FOREIGN KEY([InvoiceHeaderID])
REFERENCES [dbo].[hmlPlusOneInvoiceHeader] ([InvoiceHeaderID])
GO

ALTER TABLE [dbo].[hmlPlusOneInvoiceLine] CHECK CONSTRAINT [FK_hmlPlusOneInvoiceLine_Header]
GO

CREATE UNIQUE NONCLUSTERED INDEX [UX_hmlPlusOneInvoiceLine_BatchDocumentLine]
ON [dbo].[hmlPlusOneInvoiceLine]([ImportBatchID] ASC, [SupplierID] ASC, [DocumentNo] ASC, [SourceLineNo] ASC)
GO

CREATE NONCLUSTERED INDEX [IX_hmlPlusOneInvoiceLine_Header]
ON [dbo].[hmlPlusOneInvoiceLine]([InvoiceHeaderID] ASC, [SourceLineNo] ASC)
INCLUDE ([Status], [LineValueExclGST], [LineValueGST], [LedgerCode], [LineDescription])
GO

CREATE NONCLUSTERED INDEX [IX_hmlPlusOneInvoiceLine_Status]
ON [dbo].[hmlPlusOneInvoiceLine]([Status] ASC, [Processed] ASC)
INCLUDE ([InvoiceHeaderID], [SourceLineNo], [LedgerCode], [LineMessage])
GO
