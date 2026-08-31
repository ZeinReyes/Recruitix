function StatCard({ title, value, description }) {
  return (
    <div className="stat-card">
      <div className="stat-card-title">{title}</div>

      <div className="stat-card-value">
        {value}
      </div>

      {description && (
        <div className="stat-card-description">
          {description}
        </div>
      )}
    </div>
  );
}

export default StatCard;