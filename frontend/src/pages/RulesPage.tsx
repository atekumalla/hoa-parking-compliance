export default function RulesPage() {
  return (
    <div className="card">
      <span className="eyebrow">Reference</span>
      <h2>Parking Enforcement Rules</h2>

      <h3>General Parking Requirements</h3>
      <ol>
        <li>Every vehicle parked in guest/visitor spots must display an HOA-issued placard or paper parking tag at all times.</li>
        <li>Vehicles without a valid tag or placard are subject to immediate towing without warning.</li>
      </ol>

      <hr />

      <h3>9-Day / 30-Day Rule</h3>
      <ol start={3}>
        <li>
          Guest vehicles cannot be parked more than 9 unique days in any rolling 30-day period.
          <ul>
            <li>Multiple sightings on the same calendar day count as 1 day.</li>
            <li>The 30-day window rolls forward daily (it is not a fixed calendar month).</li>
          </ul>
        </li>
      </ol>

      <hr />

      <h3>Warning &amp; Towing Policy</h3>
      <ol start={4}>
        <li>
          <strong>First violation</strong> (more than 9 days in a 30-day period):
          <ul>
            <li>The vehicle must receive one written warning.</li>
            <li>The warning is logged with a timestamp.</li>
          </ul>
        </li>
        <li>
          <strong>Continued parking after warning</strong> (same 30-day period):
          <ul><li>The vehicle is eligible for towing immediately — no additional warning required.</li></ul>
        </li>
        <li>
          <strong>Future violations</strong> (different 30-day period, but vehicle was previously warned):
          <ul><li>The vehicle is eligible for towing immediately — the prior warning carries forward permanently.</li></ul>
        </li>
      </ol>

      <hr />

      <h3>Summary Table</h3>
      <table>
        <thead>
          <tr><th>Scenario</th><th>Action</th></tr>
        </thead>
        <tbody>
          <tr><td>No tag/placard displayed</td><td>Tow immediately</td></tr>
          <tr><td>≤ 9 unique days in 30-day window</td><td>Compliant — no action</td></tr>
          <tr><td>&gt; 9 days, never warned before</td><td>Issue warning</td></tr>
          <tr><td>&gt; 9 days, warned in current period</td><td>Eligible for tow</td></tr>
          <tr><td>&gt; 9 days, warned in a prior period</td><td>Eligible for tow</td></tr>
        </tbody>
      </table>

      <hr />

      <h3>Notes</h3>
      <ul>
        <li>Warnings are permanent — once a vehicle has been warned, any future 9-day violation in any period makes it immediately eligible for towing.</li>
        <li>The scoreboard tracks unique parking days automatically from logged sightings.</li>
        <li>Always log a sighting before issuing a warning or tow so the record is complete.</li>
      </ul>
    </div>
  )
}
