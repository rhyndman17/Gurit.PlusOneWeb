USE [HMNZL]
GO

SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE OR ALTER VIEW [dbo].[vw_hmlPlusOneInvoiceLineDetail]
AS
SELECT
    h.[InvoiceHeaderID],
    l.[InvoiceLineID],
    l.[SourceLineNo],
    UPPER(RTRIM(h.[SupplierID])) AS [SupplierID],
    RTRIM(h.[DocumentNo]) AS [DocumentNo],
    h.[DocumentDate],
    h.[AccountingValueDate],
    RTRIM(h.[FileName]) AS [FileName],
    RTRIM(h.[ImageURL]) AS [ImageURL],
    RTRIM(l.[GLDimension1]) AS [GLDimension1],
    RTRIM(l.[GLDimension2]) AS [GLDimension2],
    RTRIM(l.[LedgerCode]) AS [LedgerCode],
    l.[LineValueExclGST],
    l.[LineValueGST],
    l.[UnitValueExclGST],
    l.[UnitValueGST],
    RTRIM(l.[LineDescription]) AS [LineDescription],
    RTRIM(l.[PurchaseOrderNo]) AS [PurchaseOrderNo],
    l.[POLine],
    l.[InvoicedQty],
    RTRIM(l.[GLDimension3]) AS [GLDimension3],
    l.[Status] AS [LineStatus],
    CASE
        WHEN l.[Status] = 0 THEN 'Ready'
        WHEN l.[Status] = 1 THEN 'Processing'
        WHEN l.[Status] = 2 THEN 'Processed'
        WHEN l.[Status] = 9 THEN 'Error'
        ELSE 'Status ' + CONVERT(varchar(10), l.[Status])
    END AS [LineStatusDesc],
    CASE
        WHEN l.[Status] = 9
          OR NULLIF(LTRIM(RTRIM(ISNULL(l.[LineMessage], ''))), '') IS NOT NULL
        THEN 1
        ELSE 0
    END AS [HasLineError],
    NULLIF(LTRIM(RTRIM(ISNULL(l.[LineMessage], ''))), '') AS [LineMessage],
    l.[ErrorState],
    h.[Status] AS [HeaderStatus],
    CASE
        WHEN h.[Status] = 0 THEN 'Ready'
        WHEN h.[Status] = 1 THEN 'Processing'
        WHEN h.[Status] = 2 THEN 'Processed'
        WHEN h.[Status] = 9 THEN 'Error'
        ELSE 'Status ' + CONVERT(varchar(10), h.[Status])
    END AS [HeaderStatusDesc],
    NULLIF(LTRIM(RTRIM(ISNULL(h.[HeaderMessage], ''))), '') AS [HeaderMessage],
    RTRIM(h.[GPVoucherNumber]) AS [GPVoucherNumber],
    RTRIM(h.[GPBatchID]) AS [GPBatchID],
    l.[Processed] AS [LineProcessedDateTime],
    h.[Processed] AS [HeaderProcessedDateTime]
FROM [dbo].[hmlPlusOneInvoiceLine] l
INNER JOIN [dbo].[hmlPlusOneInvoiceHeader] h
    ON h.[InvoiceHeaderID] = l.[InvoiceHeaderID];
GO
