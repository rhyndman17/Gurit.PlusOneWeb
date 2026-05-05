USE [HMNZL]
GO

/*
    Clears the split PlusOne staging tables using TRUNCATE.

    Why the FK drop/recreate is needed:
    SQL Server will not allow TRUNCATE TABLE on dbo.hmlPlusOneInvoiceHeader
    while dbo.hmlPlusOneInvoiceLine has a foreign key referencing it.
*/

SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

SET XACT_ABORT ON;
GO

BEGIN TRY
    BEGIN TRAN;

    ALTER TABLE dbo.hmlPlusOneInvoiceLine
        DROP CONSTRAINT [FK_hmlPlusOneInvoiceLine_Header];

    TRUNCATE TABLE dbo.hmlPlusOneInvoiceLine;
    TRUNCATE TABLE dbo.hmlPlusOneInvoiceHeader;

    ALTER TABLE dbo.hmlPlusOneInvoiceLine WITH CHECK
        ADD CONSTRAINT [FK_hmlPlusOneInvoiceLine_Header]
        FOREIGN KEY ([InvoiceHeaderID])
        REFERENCES dbo.hmlPlusOneInvoiceHeader ([InvoiceHeaderID]);

    ALTER TABLE dbo.hmlPlusOneInvoiceLine
        CHECK CONSTRAINT [FK_hmlPlusOneInvoiceLine_Header];

    COMMIT TRAN;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
    BEGIN
        ROLLBACK TRAN;
    END;

    THROW;
END CATCH;
GO
