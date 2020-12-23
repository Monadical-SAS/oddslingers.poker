import React from 'react'

import Button from 'react-bootstrap/lib/Button'
import FormControl from 'react-bootstrap/lib/FormControl'
import FormGroup from 'react-bootstrap/lib/FormGroup'
import InputGroup from 'react-bootstrap/lib/InputGroup'

import {Icon} from '@/components/icons'


const InputGroupButton = InputGroup.Button


export const SearchField = ({onSearch, onChange, text='Search', width=250, bsStyle='default', icon='search', ...props}) => {
    const id = props.id || 'search-field'
    const onSubmit = (event) => {
        event.preventDefault()
        const query = $(`#${id}`).val()
        onSearch(query)
    }
    const search_form_style = `
        form.search-field {
            display: inline-block;
            width: ${width}px;
            vertical-align: bottom;
            margin-bottom: 0px;
        }
        form.search-field .form-group {
            margin-bottom: 0px;
        }
    `
    return <span>
        <style>{search_form_style}</style>
        <form action="#" onSubmit={onSubmit} className="search-field">
            <FormGroup>
                <InputGroup>
                    <FormControl type="search" id={id} {...props} onChange={() => {onChange($(`#${id}`).val())}}/>
                    <InputGroupButton>
                        <Button bsStyle={bsStyle} onClick={onSubmit} type="submit">
                            <Icon name={icon}/> {text}
                        </Button>
                    </InputGroupButton>
                </InputGroup>
            </FormGroup>
        </form>
    </span>
}
