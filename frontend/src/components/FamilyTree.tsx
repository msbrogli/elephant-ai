import type { Person, Group } from '../pages/PeopleGraph'
import PersonCard from './PersonCard'

interface FamilyTreeSection {
  key: string
  label: string
  people: Person[]
}

export function buildFamilyTree(people: Person[], _groups: Group[]): FamilyTreeSection[] {
  const sections: Record<string, Person[]> = {
    parents: [],
    siblings: [],
    core: [],
    inlaws: [],
    children: [],
    other: [],
  }

  for (const person of people) {
    const rels = person.relationship.map(r => r.toLowerCase())

    if (rels.includes('self') || rels.some(r => ['wife', 'husband', 'spouse'].includes(r))) {
      sections.core.push(person)
    } else if (rels.some(r => ['father', 'mother', 'parent'].includes(r))) {
      sections.parents.push(person)
    } else if (rels.some(r => ['brother', 'sister', 'sibling'].includes(r))) {
      sections.siblings.push(person)
    } else if (rels.some(r => r.includes('-in-law'))) {
      sections.inlaws.push(person)
    } else if (rels.some(r => ['son', 'daughter', 'child'].includes(r))) {
      sections.children.push(person)
    } else {
      sections.other.push(person)
    }
  }

  // Sort core: self first, then spouse
  sections.core.sort((a, b) => {
    const aIsSelf = a.relationship.includes('self') ? 0 : 1
    const bIsSelf = b.relationship.includes('self') ? 0 : 1
    return aIsSelf - bIsSelf
  })

  const ordered: { key: string; label: string }[] = [
    { key: 'parents', label: 'Parents' },
    { key: 'siblings', label: 'Siblings' },
    { key: 'core', label: '' },
    { key: 'inlaws', label: 'In-Laws' },
    { key: 'children', label: 'Children' },
    { key: 'other', label: 'Other' },
  ]

  return ordered
    .filter(s => sections[s.key].length > 0)
    .map(s => ({ key: s.key, label: s.label, people: sections[s.key] }))
}

interface FamilyTreeProps {
  people: Person[]
  groups: Group[]
  selected: Person | null
  onSelect: (person: Person) => void
}

export default function FamilyTree({ people, groups, selected, onSelect }: FamilyTreeProps) {
  const sections = buildFamilyTree(people, groups)

  return (
    <div className="family-tree">
      {sections.map((section, i) => (
        <div key={section.key} className={`family-tree__section family-tree__section--${section.key}`}>
          {i > 0 && <div className="family-tree__connector" />}
          {section.label && <div className="family-tree__label">{section.label}</div>}
          <div className="family-tree__row">
            {section.people.map(person => (
              <PersonCard
                key={person.person_id}
                person={person}
                groups={groups}
                isSelected={selected?.person_id === person.person_id}
                onClick={onSelect}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
