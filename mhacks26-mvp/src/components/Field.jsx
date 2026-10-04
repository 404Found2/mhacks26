function Field({ label, value, alignment, select }) {
  return (
    <div className="field-block">
      <label className="field-label">{label}</label>
      {select ? (
        <div className="input select-input">
          <span>{value}</span>
          <span className="caret">⌄</span>
        </div>
      ) : (
        <input className={`input ${alignment === 'right' ? 'align-right' : ''}`} value={value} readOnly />
      )}
    </div>
  );
}

export default Field;
