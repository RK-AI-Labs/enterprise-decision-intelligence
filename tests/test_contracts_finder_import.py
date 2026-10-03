from decimal import Decimal

from ai_template_python.data_foundation.contracts_finder import (
    iter_contracts_finder_notices,
)


def test_contracts_finder_parser_preserves_nulls_zero_and_awards(tmp_path) -> None:
    source = tmp_path / "notices.xml"
    source.write_text(
        """<?xml version="1.0"?>
<ArrayOfFullNotice xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <FullNotice>
    <Id>notice-1</Id>
    <Notice>
      <Id>notice-1</Id><Identifier>CF-1</Identifier><Title>Example award</Title>
      <Description>Public notice</Description><Status>Awarded</Status>
      <OrganisationName>Public Buyer</OrganisationName><Type>Contract</Type>
      <ContactDetails><Email>private@example.test</Email></ContactDetails>
      <CpvCodes><CpvCode><Code>48000000</Code></CpvCode></CpvCodes>
      <PublishedDate>2026-09-23T18:12:28+01:00</PublishedDate>
      <ValueLow>0</ValueLow><ValueHigh xsi:nil="true" />
      <Postcode xsi:nil="true" />
    </Notice>
    <Awards><AwardDetail><Id>award-1</Id><SupplierName>Supplier Ltd</SupplierName>
      <Value>1250.25</Value><StartDate>2026-10-01T00:00:00Z</StartDate>
    </AwardDetail></Awards>
  </FullNotice>
</ArrayOfFullNotice>""",
        encoding="utf-8",
    )

    [notice] = list(iter_contracts_finder_notices(source))

    assert notice.source_notice_id == "notice-1"
    assert notice.status == "Awarded"
    assert notice.value_low_gbp == Decimal("0")
    assert notice.value_high_gbp is None
    assert notice.postcode is None
    assert "ContactDetails" not in notice.raw_notice
    assert "48000000" in str(notice.raw_notice["CpvCodes"])
    assert notice.awards[0].supplier_name == "Supplier Ltd"
    assert notice.awards[0].awarded_value_gbp == Decimal("1250.25")
    assert notice.awards[0].start_date is not None
    assert notice.awards[0].start_date.utcoffset().total_seconds() == 0
