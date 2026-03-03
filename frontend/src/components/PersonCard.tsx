import type { Person, Group } from '../pages/PeopleGraph'

interface PersonCardProps {
  person: Person
  groups: Group[]
  isSelected: boolean
  onClick: (person: Person) => void
}

export default function PersonCard({ person, groups, isSelected, onClick }: PersonCardProps) {
  const groupColor = person.groups
    .map(gid => groups.find(g => g.group_id === gid))
    .find(g => g?.color)?.color ?? null

  const isSelf = person.relationship.includes('self')

  return (
    <button
      className={`person-card${isSelected ? ' person-card--selected' : ''}${isSelf ? ' person-card--self' : ''}`}
      onClick={() => onClick(person)}
      type="button"
    >
      <div className="person-card__header">
        {groupColor && (
          <span className="person-card__dot" style={{ backgroundColor: groupColor }} />
        )}
        <span className="person-card__name">{person.display_name}</span>
      </div>
      <span className="person-card__rel">{person.relationship.join(', ')}</span>
      {person.birthday && (
        <span className="person-card__birthday">{person.birthday}</span>
      )}
    </button>
  )
}
