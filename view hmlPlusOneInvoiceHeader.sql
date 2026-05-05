USE [HMNZL]
GO

SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE OR ALTER VIEW [dbo].[vw_hmlPlusOneInvoiceHeader]
AS
SELECT
    h.[InvoiceHeaderID],
    h.[ImportBatchID],
    RTRIM(h.[DocumentNo]) AS [DocumentNo],
    UPPER(RTRIM(h.[SupplierID])) AS [SupplierID],
    ISNULL(NULLIF(RTRIM(v.[VENDNAME]), ''), '*** invalid vendor ***') AS [VendorName],
    h.[DocumentDate],
    h.[AccountingValueDate],
    RTRIM(h.[FileName]) AS [FileName],
    RTRIM(h.[ImageURL]) AS [ImageURL],
    COUNT(l.[InvoiceLineID]) AS [LineCount],
    ISNULL(SUM(ISNULL(l.[LineValueExclGST], 0)), 0) AS [SubtotalExclGST],
    ISNULL(SUM(ISNULL(l.[LineValueGST], 0)), 0) AS [TotalGST],
    ISNULL(SUM(ISNULL(l.[LineValueExclGST], 0) + ISNULL(l.[LineValueGST], 0)), 0) AS [DocumentTotal],
    h.[Status] AS [HeaderStatus],
    CASE
        WHEN h.[Status] = 0 THEN 'Ready'
        WHEN h.[Status] = 1 THEN 'Processing'
        WHEN h.[Status] = 2 THEN 'Processed'
        WHEN h.[Status] = 9 THEN 'Error'
        ELSE 'Status ' + CONVERT(varchar(10), h.[Status])
    END AS [HeaderStatusDesc],
    CASE
        WHEN h.[Status] = 9
          OR NULLIF(LTRIM(RTRIM(ISNULL(h.[HeaderMessage], ''))), '') IS NOT NULL
        THEN 1
        ELSE 0
    END AS [HasHeaderError],
    ISNULL(SUM(
        CASE
            WHEN l.[Status] = 9
              OR NULLIF(LTRIM(RTRIM(ISNULL(l.[LineMessage], ''))), '') IS NOT NULL
            THEN 1
            ELSE 0
        END
    ), 0) AS [ErrorLineCount],
    MIN(
        CASE
            WHEN l.[Status] = 9
              OR NULLIF(LTRIM(RTRIM(ISNULL(l.[LineMessage], ''))), '') IS NOT NULL
            THEN l.[SourceLineNo]
            ELSE NULL
        END
    ) AS [FirstErrorSourceLineNo],
    CASE
        WHEN h.[Status] = 9
          OR NULLIF(LTRIM(RTRIM(ISNULL(h.[HeaderMessage], ''))), '') IS NOT NULL
          OR ISNULL(SUM(
                CASE
                    WHEN l.[Status] = 9
                      OR NULLIF(LTRIM(RTRIM(ISNULL(l.[LineMessage], ''))), '') IS NOT NULL
                    THEN 1
                    ELSE 0
                END
            ), 0) > 0
        THEN 1
        ELSE 0
    END AS [HasErrors],
    NULLIF(LTRIM(RTRIM(ISNULL(h.[HeaderMessage], ''))), '') AS [HeaderMessage],
    RTRIM(h.[GPVoucherNumber]) AS [GPVoucherNumber],
    RTRIM(h.[GPBatchID]) AS [GPBatchID],
    h.[Processed] AS [ProcessedDateTime],
    h.[CreatedDateTime],
    h.[LastUpdatedDateTime]
FROM [dbo].[hmlPlusOneInvoiceHeader] h
LEFT JOIN [dbo].[hmlPlusOneInvoiceLine] l
    ON l.[InvoiceHeaderID] = h.[InvoiceHeaderID]
LEFT JOIN [dbo].[PM00200] v
    ON v.[VENDORID] = h.[SupplierID]
GROUP BY
    h.[InvoiceHeaderID],
    h.[ImportBatchID],
    h.[DocumentNo],
    h.[SupplierID],
    v.[VENDNAME],
    h.[DocumentDate],
    h.[AccountingValueDate],
    h.[FileName],
    h.[ImageURL],
    h.[Status],
    h.[HeaderMessage],
    h.[GPVoucherNumber],
    h.[GPBatchID],
    h.[Processed],
    h.[CreatedDateTime],
    h.[LastUpdatedDateTime];
GO
