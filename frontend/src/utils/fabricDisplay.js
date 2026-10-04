export const fabricObservation = (observation) => observation?.value == null ? 'Not recorded'
  : `${observation.value} ${String(observation.unit || '').replace(/m2/g, 'm²')}`.trim();

export const fabricGoal = (criterion, goal) => criterion?.goal_options?.find((option) => option.value === goal)?.label
  || (goal === 'cost' ? 'Smaller measured value' : goal === 'benefit' ? 'Larger measured value' : 'Not set');

export const fabricDescription = (fabric, study) => fabric.study_id
  ? [study?.composition || fabric.technical_details?.composition_note,
    fabric.research_sample?.structure || fabric.technical_details?.construction].filter(Boolean).join(' · ') || fabric.simple_description
  : fabric.simple_description;
