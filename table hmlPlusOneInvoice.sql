SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE TABLE [dbo].[hmlPlusOneInvoice](
	[GLDimension1] [char](20) NULL,
	[GLDimension2] [char](20) NULL,
	[SupplierID] [char](15) NULL,
	[DocumentDate] [datetime] NULL,
	[AccountingValueDate] [datetime] NULL,
	[DocumentNo] [char](21) NULL,
	[ImageURL] [char](200) NULL,
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
	[Status] [int] NULL,
	[Processed] [datetime] NULL,
	[FileName] [char](200) NULL,
	[IntgrMessages] [varchar](max) NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

ALTER TABLE [dbo].[hmlPlusOneInvoice] ADD  CONSTRAINT [DF_hmlPlusOneInvoice_UnitValueExclGST]  DEFAULT ((0)) FOR [UnitValueExclGST]
GO

ALTER TABLE [dbo].[hmlPlusOneInvoice] ADD  CONSTRAINT [DF_hmlPlusOneInvoice_UnitValueGST]  DEFAULT ((0)) FOR [UnitValueGST]
GO


