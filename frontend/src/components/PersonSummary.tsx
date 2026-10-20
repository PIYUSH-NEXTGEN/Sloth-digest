interface PersonSummaryProps {
  name: string;
  points: string[];
}

export default function PersonSummary({ name, points }: PersonSummaryProps) {
  return (
    <div className="person-summary">
      <h4>{name}</h4>
      <ul>
        {points.map((point) => (
          <li key={point}>{point}</li>
        ))}
      </ul>
    </div>
  );
}
