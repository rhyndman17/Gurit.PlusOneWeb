
/****** Object:  View [dbo].[PlusOneSUP]    Script Date: 2026-05-11 8:53:39 PM ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO


CREATE view [dbo].[PlusOneSUP] as

select 
rtrim(v.VENDORID) 'SupplierID', rtrim(v.VENDSHNM) 'SupplierCrossRef', rtrim(v.VENDNAME) 'SupplierName', 
rtrim(v.ADDRESS1) 'SupplierAddressL1', rtrim(v.ADDRESS2) 'SupplierAddressL2',rtrim(v.ADDRESS3) 'SupplierAddressL3',
'' as 'SupplierAddressL4', rtrim(v.ZIPCODE) 'SupplierPostcode', rtrim(v.COUNTRY) 'SupplierCountry',
rtrim(v.VNDCNTCT) 'SupplierContact',rtrim(v.PHNUMBR1) 'SupplierPhone',rtrim(v.FAXNUMBR) 'SupplierFax', isnull(rtrim(i.INET1),'') 'SupplierEmail',
'' as 'PaymentMeans', rtrim(v.CURNCYID) 'Currency', '' as 'CurrencyDesc', '' as 'SupplierAccountName',
'' as 'SupplierBankName', '' as 'SupplierBankBranch', '' as 'SupplierAccountNo',rtrim(v.TXIDNMBR) as 'SupplierTaxID',rtrim(v.TAXSCHID) 'SupplierTaxCode',isnull(cast(t.TXDTLPCT as char(12)),'') 'SupplierTaxRate','' as 'SupplierNotes',
isnull(rtrim(g.ACTNUMST),'') 'SupplierDefaultCoding','Y' 'SupplierPOFlag'
from PM00200 v
left join SY01200 i on i.Master_ID=v.VENDORID and i.ADRSCODE=v.VADDCDPR
left join TX00201 t on t.TAXDTLID=v.TAXSCHID
left join GL00105 g on g.ACTINDX=v.PMPRCHIX
where v.VENDSTTS=1 and v.HOLD=0 and
		v.VENDORID in (select VENDORID from IV00103)
union
select 
rtrim(v.VENDORID) 'SupplierID', rtrim(v.VENDSHNM) 'SupplierCrossRef', rtrim(v.VENDNAME) 'SupplierName', 
rtrim(v.ADDRESS1) 'SupplierAddressL1', rtrim(v.ADDRESS2) 'SupplierAddressL2',rtrim(v.ADDRESS3) 'SupplierAddressL3',
'' as 'SupplierAddressL4', rtrim(v.ZIPCODE) 'SupplierPostcode', rtrim(v.COUNTRY) 'SupplierCountry',
rtrim(v.VNDCNTCT) 'SupplierContact',rtrim(v.PHNUMBR1) 'SupplierPhone',rtrim(v.FAXNUMBR) 'SupplierFax', isnull(rtrim(i.INET1),'') 'SupplierEmail',
'' as 'PaymentMeans', rtrim(v.CURNCYID) 'Currency', '' as 'CurrencyDesc', '' as 'SupplierAccountName',
'' as 'SupplierBankName', '' as 'SupplierBankBranch', '' as 'SupplierAccountNo',rtrim(v.TXIDNMBR) as 'SupplierTaxID',rtrim(v.TAXSCHID) 'SupplierTaxCode',isnull(cast(t.TXDTLPCT as char(12)),'') 'SupplierTaxRate','' as 'SupplierNotes',
isnull(rtrim(g.ACTNUMST),'') 'SupplierDefaultCoding','N' 'SupplierPOFlag'
from PM00200 v
left join SY01200 i on i.Master_ID=v.VENDORID and i.ADRSCODE=v.VADDCDPR
left join TX00201 t on t.TAXDTLID=v.TAXSCHID
left join GL00105 g on g.ACTINDX=v.PMPRCHIX
where v.VENDSTTS=1 and v.HOLD=0 and
		v.VENDORID not in (select VENDORID from IV00103)
GO


